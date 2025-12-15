"""
Prediction Result Caching for RetainWise

Implements:
1. Result caching (avoid reprocessing identical CSVs)
2. Cache invalidation
3. Cache statistics

Goal: Reduce duplicate ML computations by 30-50%

Author: RetainWise Engineering
Date: December 15, 2025
Version: 1.0
"""

import hashlib
import json
import pickle
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import redis.asyncio as redis

from backend.core.observability import production_logger

# ========================================
# PREDICTION CACHE
# ========================================

class PredictionCache:
    """
    Redis-based caching for prediction results
    
    Why Cache Predictions?
    ----------------------
    User uploads same CSV twice:
    - Without cache: Process again (850ms, $0.00002 cost)
    - With cache: Return instantly (<10ms, $0 cost)
    
    Cache Hit Rate:
    ---------------
    Typical: 30-50% (users re-upload same data)
    Savings: 30-50% compute cost reduction
    
    Cache Key Strategy:
    -------------------
    Hash CSV content + model version
    
    Example:
    customer1.csv (100 rows) + model_v1.0
    → cache_key = sha256("content+v1.0") = "a3b2c1d4..."
    
    Cache TTL (Time-To-Live):
    --------------------------
    7 days (prediction results rarely change)
    
    Memory Usage:
    -------------
    Average prediction: 50KB (100 rows * 500 bytes)
    Cache size: 1000 predictions = 50MB
    Redis instance: 512MB = 10K cached predictions
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.cache_ttl_seconds = 7 * 24 * 3600  # 7 days
        self.enabled = False  # Will be set to True if Redis connects
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0
        }
    
    async def connect(self):
        """Initialize Redis connection (gracefully fails if Redis unavailable)"""
        if not self.redis_client:
            try:
                self.redis_client = await redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=False  # Store binary data (pickle)
                )
                self.enabled = True
                production_logger.logger.info(
                    "cache_connected",
                    redis_url=self.redis_url.split('@')[-1],  # Hide password
                    severity="INFO"
                )
            except Exception as e:
                self.enabled = False
                production_logger.logger.warning(
                    "cache_connection_failed",
                    error=str(e),
                    message="Caching disabled - predictions will work without cache",
                    severity="WARNING"
                )
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    def generate_cache_key(
        self,
        csv_content: bytes,
        model_version: str = "saas_baseline_v1.0"
    ) -> str:
        """
        Generate cache key from CSV content
        
        Why Hash Content?
        -----------------
        - Same CSV uploaded by different users → same hash
        - Filename irrelevant (customer1.csv vs test.csv)
        - Even 1 byte change → different hash (cache miss)
        
        Hash Function: SHA-256
        ----------------------
        - Cryptographically secure
        - Collision probability: ~0 for practical purposes
        - Fast (hash 1MB in <10ms)
        
        Args:
        -----
        csv_content: Raw CSV file bytes
        model_version: Model version (invalidate cache on model update)
        
        Returns:
        --------
        Cache key: "prediction:{hash}"
        
        Example:
        --------
        csv = b"customerID,total_spend\nCUST001,1000\n"
        key = generate_cache_key(csv, "v1.0")
        # → "prediction:a3b2c1d4e5f6..."
        """
        hasher = hashlib.sha256()
        hasher.update(csv_content)
        hasher.update(model_version.encode())
        hash_hex = hasher.hexdigest()
        
        return f"prediction:{hash_hex}"
    
    async def get(
        self,
        cache_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached prediction result
        
        Returns:
        --------
        {
          "prediction_id": "...",
          "s3_output_key": "...",
          "rows_processed": 100,
          "cached_at": "2025-12-15T10:00:00Z",
          "model_version": "saas_baseline_v1.0"
        }
        or None if cache miss
        """
        await self.connect()
        
        # If Redis unavailable, always return cache miss
        if not self.enabled:
            return None
        
        try:
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                # Cache hit!
                self.stats["hits"] += 1
                
                result = pickle.loads(cached_data)
                
                production_logger.logger.info(
                    "cache_hit",
                    cache_key=cache_key[:16],  # First 16 chars
                    cached_at=result.get("cached_at"),
                    severity="INFO"
                )
                
                return result
            else:
                # Cache miss
                self.stats["misses"] += 1
                
                production_logger.logger.info(
                    "cache_miss",
                    cache_key=cache_key[:16],
                    severity="INFO"
                )
                
                return None
        
        except Exception as e:
            production_logger.logger.error(
                "cache_get_error",
                error_type=type(e).__name__,
                error_message=str(e),
                severity="ERROR"
            )
            # Fail gracefully (don't crash app if cache fails)
            return None
    
    async def set(
        self,
        cache_key: str,
        prediction_result: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ):
        """
        Cache prediction result
        
        Args:
        -----
        cache_key: Cache key from generate_cache_key()
        prediction_result: Prediction metadata to cache
        ttl_seconds: TTL override (default: 7 days)
        """
        await self.connect()
        
        # If Redis unavailable, silently skip caching
        if not self.enabled:
            return
        
        ttl = ttl_seconds or self.cache_ttl_seconds
        
        try:
            # Add cache metadata
            prediction_result["cached_at"] = datetime.utcnow().isoformat()
            
            # Serialize to pickle (more efficient than JSON for complex objects)
            cached_data = pickle.dumps(prediction_result)
            
            # Store in Redis with TTL
            await self.redis_client.setex(
                cache_key,
                ttl,
                cached_data
            )
            
            self.stats["sets"] += 1
            
            production_logger.logger.info(
                "cache_set",
                cache_key=cache_key[:16],
                ttl_seconds=ttl,
                data_size_kb=len(cached_data) / 1024,
                severity="INFO"
            )
        
        except Exception as e:
            production_logger.logger.error(
                "cache_set_error",
                error_type=type(e).__name__,
                error_message=str(e),
                severity="ERROR"
            )
            # Fail gracefully
    
    async def invalidate(self, cache_key: str):
        """Delete cached result"""
        await self.connect()
        
        try:
            await self.redis_client.delete(cache_key)
            
            production_logger.logger.info(
                "cache_invalidated",
                cache_key=cache_key[:16],
                severity="INFO"
            )
        
        except Exception as e:
            production_logger.logger.error(
                "cache_invalidate_error",
                error_type=type(e).__name__,
                error_message=str(e),
                severity="ERROR"
            )
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
        --------
        {
          "hits": 150,
          "misses": 50,
          "hit_rate": 0.75,
          "total_keys": 200,
          "memory_used_mb": 10.5
        }
        """
        await self.connect()
        
        try:
            # Get Redis info
            info = await self.redis_client.info("stats")
            memory_info = await self.redis_client.info("memory")
            
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0
            
            return {
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "hit_rate": round(hit_rate, 3),
                "sets": self.stats["sets"],
                "total_keys": await self.redis_client.dbsize(),
                "memory_used_mb": round(
                    int(memory_info.get("used_memory", 0)) / 1024 / 1024,
                    2
                )
            }
        
        except Exception as e:
            production_logger.logger.error(
                "cache_stats_error",
                error_type=type(e).__name__,
                error_message=str(e),
                severity="ERROR"
            )
            return {"error": str(e)}
    
    async def clear_all(self):
        """Clear entire cache (use with caution!)"""
        await self.connect()
        
        try:
            await self.redis_client.flushdb()
            
            production_logger.logger.warning(
                "cache_cleared",
                severity="WARNING"
            )
        
        except Exception as e:
            production_logger.logger.error(
                "cache_clear_error",
                error_type=type(e).__name__,
                error_message=str(e),
                severity="ERROR"
            )


# ========================================
# SINGLETON INSTANCE
# ========================================

# Global cache instance
prediction_cache = PredictionCache(
    redis_url="redis://localhost:6379"  # Override with env var in production
)

# ========================================
# MODULE INFO
# ========================================

__all__ = [
    'PredictionCache',
    'prediction_cache'
]

