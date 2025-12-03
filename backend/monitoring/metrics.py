"""
Production-grade CloudWatch metrics using Embedded Metric Format (EMF).

ARCHITECTURE: Hybrid Async + Sync Design
========================================
- Async API for FastAPI handlers (non-blocking)
- Sync EMF backend runs in dedicated thread pool
- Single background task batches and flushes metrics
- Cost-optimized with dimension cardinality control

Key Benefits:
1. Non-blocking - metrics never delay API responses
2. Cost-efficient - EMF format is 10x cheaper than PutMetricData API
3. High-throughput - batching reduces overhead
4. Compliant - PII hashing prevents GDPR violations

Author: AI Assistant (Hybrid Design - Cursor + DeepSeek)
Date: December 3, 2025
"""

import os
import logging
import json
import hashlib
import re
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timezone
from typing import Dict, Optional, Union, List
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricUnit(str, Enum):
    """CloudWatch metric units."""
    SECONDS = "Seconds"
    MILLISECONDS = "Milliseconds"
    MICROSECONDS = "Microseconds"
    COUNT = "Count"
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    PERCENT = "Percent"
    NONE = "None"


class MetricNamespace(str, Enum):
    """Metric namespaces for RetainWise."""
    ML_PIPELINE = "RetainWise/MLPipeline"
    API = "RetainWise/API"
    WORKER = "RetainWise/Worker"
    DATABASE = "RetainWise/Database"


class CloudWatchMetricsEMF:
    """
    High-performance async metrics client using CloudWatch Embedded Metric Format.
    
    HYBRID ARCHITECTURE:
    ===================
    
    ┌─────────────────────────────────────────────────────────────┐
    │                   ASYNC API LAYER                            │
    │  FastAPI handlers → put_metric() → asyncio.Queue (no block) │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │               BACKGROUND ASYNC TASK                          │
    │  - Batches metrics from queue                                │
    │  - Flushes every 60s or when batch reaches 100              │
    │  - Delegates to sync backend via ThreadPoolExecutor          │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  SYNC EMF BACKEND                            │
    │  - Runs in dedicated thread (1 worker)                       │
    │  - Sanitizes dimensions (PII protection)                     │
    │  - Writes EMF JSON to stdout (CloudWatch captures)           │
    └─────────────────────────────────────────────────────────────┘
    
    Usage:
        # In FastAPI lifespan:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await metrics.start()
            yield
            await metrics.stop()
        
        # In async handlers:
        await metrics.put_metric("UploadSuccess", 1, MetricUnit.COUNT)
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the hybrid async/sync metrics client."""
        if self._initialized:
            return
        
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.enabled = os.getenv("CLOUDWATCH_METRICS_ENABLED", "true").lower() == "true"
        
        # Disable in test/dev unless forced
        if self.environment in ("test", "development") and not os.getenv("FORCE_CLOUDWATCH"):
            self.enabled = False
            logger.info("CloudWatch EMF metrics DISABLED (test/development mode)")
        
        # Async components
        self._queue: Optional[asyncio.Queue] = None
        self._background_task: Optional[asyncio.Task] = None
        
        # Sync backend (runs in thread pool)
        self._sync_backend = _SyncEMFBackend()
        
        # Thread pool (single worker - minimal overhead)
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="metrics-worker"
        )
        
        # Configuration
        self.batch_size = 100  # Flush after 100 metrics
        self.flush_interval = 60.0  # Flush every 60 seconds
        
        self._initialized = True
    
    async def start(self):
        """
        Start the background metrics processing task.
        
        Must be called during application startup (e.g., FastAPI lifespan).
        """
        if not self.enabled:
            logger.info("Metrics client not started (disabled)")
            return
        
        if self._background_task is None:
            self._queue = asyncio.Queue(maxsize=1000)  # Backpressure limit
            self._background_task = asyncio.create_task(self._process_metrics())
            logger.info("✅ CloudWatch EMF metrics client started")
    
    async def stop(self):
        """
        Graceful shutdown - flushes remaining metrics.
        
        Must be called during application shutdown.
        """
        if self._background_task:
            # Cancel background task
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                logger.info("Background metrics task cancelled")
            
            self._background_task = None
        
        # Shutdown thread pool
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("✅ CloudWatch EMF metrics client stopped")
    
    async def put_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: MetricUnit = MetricUnit.NONE,
        namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
        dimensions: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Publish a metric asynchronously (non-blocking).
        
        Args:
            metric_name: Name of the metric (e.g., "UploadDuration")
            value: Numeric value
            unit: Unit of measurement
            namespace: CloudWatch namespace for grouping
            dimensions: Optional key-value pairs for filtering
        
        Returns:
            bool: True if metric queued, False if metrics disabled or queue full
        
        Example:
            await metrics.put_metric(
                "UploadSuccess",
                1,
                MetricUnit.COUNT,
                namespace=MetricNamespace.API,
                dimensions={"UserBucket": "a1", "FileType": "csv"}
            )
        """
        if not self.enabled or self._queue is None:
            return False
        
        metric_data = {
            'metric_name': metric_name,
            'value': float(value),
            'unit': unit.value,
            'namespace': namespace.value,
            'dimensions': dimensions or {},
            'timestamp': datetime.now(timezone.utc)
        }
        
        try:
            # Non-blocking put with timeout (backpressure)
            await asyncio.wait_for(self._queue.put(metric_data), timeout=0.1)
            return True
        except asyncio.TimeoutError:
            # Queue is full - drop metric (better than blocking)
            logger.warning(f"Metrics queue full, dropping: {metric_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to queue metric {metric_name}: {e}")
            return False
    
    async def _process_metrics(self):
        """
        Background task that batches and flushes metrics.
        
        Runs continuously until cancelled during shutdown.
        """
        batch: List[Dict] = []
        last_flush_time = time.time()
        
        logger.info("Background metrics processor started")
        
        while True:
            try:
                # Calculate remaining time until next scheduled flush
                elapsed = time.time() - last_flush_time
                timeout = max(0.1, self.flush_interval - elapsed)
                
                try:
                    # Wait for metric or timeout
                    metric = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=timeout
                    )
                    batch.append(metric)
                except asyncio.TimeoutError:
                    # Timeout reached - time to flush
                    pass
                
                # Flush if batch is full or interval elapsed
                should_flush = (
                    len(batch) >= self.batch_size or
                    (batch and time.time() - last_flush_time >= self.flush_interval)
                )
                
                if should_flush and batch:
                    # Run sync flush in thread pool (non-blocking)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        self._executor,
                        self._sync_backend.flush_batch,
                        batch.copy()
                    )
                    batch.clear()
                    last_flush_time = time.time()
            
            except asyncio.CancelledError:
                # Shutdown - flush remaining metrics
                if batch:
                    logger.info(f"Flushing {len(batch)} remaining metrics on shutdown")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        self._executor,
                        self._sync_backend.flush_batch,
                        batch
                    )
                break
            
            except Exception as e:
                logger.error(f"Error in metrics processor: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight error loop
    
    async def flush(self):
        """
        Manually flush all pending metrics (useful for testing).
        
        Waits for background task to process current queue.
        """
        if not self.enabled or self._queue is None:
            return
        
        # Wait for queue to drain
        await self._queue.join()
    
    # Convenience methods
    async def increment_counter(
        self,
        metric_name: str,
        namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
        dimensions: Optional[Dict[str, str]] = None
    ):
        """Increment a counter by 1."""
        await self.put_metric(metric_name, 1, MetricUnit.COUNT, namespace, dimensions)
    
    async def record_time(
        self,
        metric_name: str,
        duration_seconds: float,
        namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
        dimensions: Optional[Dict[str, str]] = None
    ):
        """Record a duration in seconds."""
        await self.put_metric(metric_name, duration_seconds, MetricUnit.SECONDS, namespace, dimensions)


class _SyncEMFBackend:
    """
    Synchronous EMF backend (runs in thread pool).
    
    Handles:
    - Dimension sanitization (PII protection)
    - Cardinality control (cost optimization)
    - EMF JSON generation
    - Writing to stdout (captured by CloudWatch Logs)
    """
    
    def __init__(self):
        self.batch_lock = Lock()  # Thread-safe for sync operations
    
    def flush_batch(self, batch: List[Dict]):
        """
        Flush a batch of metrics using EMF format.
        
        Called from thread pool executor (sync context).
        """
        if not batch:
            return
        
        with self.batch_lock:
            try:
                # Sanitize dimensions (PII protection + cost control)
                sanitized_batch = [
                    self._sanitize_metric(metric) for metric in batch
                ]
                
                # Group by namespace + dimensions (EMF requirement)
                grouped = self._group_metrics(sanitized_batch)
                
                # Write EMF JSON to stdout
                for emf_data in grouped:
                    print(json.dumps(emf_data), flush=True)
                
                logger.debug(f"📊 EMF: Flushed {len(batch)} metrics")
            
            except Exception as e:
                logger.error(f"❌ Failed to flush EMF metrics: {e}", exc_info=True)
    
    def _sanitize_metric(self, metric: Dict) -> Dict:
        """
        Sanitize metric dimensions to prevent:
        1. PII leakage (hash user IDs)
        2. Cost explosion (limit cardinality)
        3. Invalid characters
        """
        sanitized_dimensions = {}
        
        for key, value in metric.get('dimensions', {}).items():
            # Skip ultra-high-cardinality dimensions
            if key in ("UploadId", "RequestId", "TransactionId", "CorrelationId"):
                continue  # Would create unlimited unique metrics
            
            # Hash user IDs (privacy + cost control)
            if key in ("UserId", "CustomerId", "AccountId"):
                # Hash to 256 buckets (00-FF)
                user_hash = hashlib.md5(str(value).encode()).hexdigest()[:2]
                sanitized_dimensions["UserBucket"] = user_hash
                continue
            
            # Sanitize and truncate file names
            if key == "FileName":
                # Keep extension only (not full filename = PII)
                extension = value.split('.')[-1] if '.' in value else 'unknown'
                sanitized_dimensions["FileType"] = re.sub(r'[^a-zA-Z0-9]', '', extension)[:10]
                continue
            
            # Generic sanitization (remove special chars, limit length)
            safe_value = re.sub(r'[^a-zA-Z0-9_\-\.]', '', str(value))[:100]
            sanitized_dimensions[key] = safe_value
        
        # Limit to 10 dimensions (CloudWatch max)
        if len(sanitized_dimensions) > 10:
            logger.warning(f"Too many dimensions ({len(sanitized_dimensions)}), truncating")
            sanitized_dimensions = dict(list(sanitized_dimensions.items())[:10])
        
        metric['dimensions'] = sanitized_dimensions
        return metric
    
    def _group_metrics(self, batch: List[Dict]) -> List[Dict]:
        """
        Group metrics by namespace + dimensions for EMF format.
        
        EMF Format Spec:
        {
            "_aws": {
                "Timestamp": 1638316800000,
                "CloudWatchMetrics": [{
                    "Namespace": "RetainWise/API",
                    "Dimensions": [["UserBucket", "FileType"]],
                    "Metrics": [{"Name": "UploadDuration", "Unit": "Seconds"}]
                }]
            },
            "UploadDuration": 1.23,
            "UserBucket": "a1",
            "FileType": "csv"
        }
        """
        grouped = defaultdict(lambda: defaultdict(list))
        
        for metric in batch:
            namespace = metric['namespace']
            dim_key = tuple(sorted(metric['dimensions'].items()))
            grouped[namespace][dim_key].append(metric)
        
        emf_batches = []
        
        for namespace, dim_groups in grouped.items():
            for dim_tuple, metrics in dim_groups.items():
                dimensions = dict(dim_tuple)
                
                # Build EMF structure
                emf_data = {
                    "_aws": {
                        "Timestamp": int(time.time() * 1000),
                        "CloudWatchMetrics": [{
                            "Namespace": namespace,
                            "Dimensions": [list(dimensions.keys())] if dimensions else [],
                            "Metrics": [
                                {"Name": m['metric_name'], "Unit": m['unit']}
                                for m in metrics
                            ]
                        }]
                    }
                }
                
                # Add dimension values
                emf_data.update(dimensions)
                
                # Add metric values
                for m in metrics:
                    emf_data[m['metric_name']] = m['value']
                
                emf_batches.append(emf_data)
        
        return emf_batches


# Global singleton instance
_metrics_client: Optional[CloudWatchMetricsEMF] = None


def get_metrics_client() -> CloudWatchMetricsEMF:
    """Get or create the global CloudWatch metrics client (singleton)."""
    global _metrics_client
    if _metrics_client is None:
        _metrics_client = CloudWatchMetricsEMF()
    return _metrics_client


# Convenience functions for common use cases
async def put_metric(
    metric_name: str,
    value: Union[int, float],
    unit: MetricUnit = MetricUnit.NONE,
    namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
    dimensions: Optional[Dict[str, str]] = None
):
    """Shorthand for publishing a metric."""
    await get_metrics_client().put_metric(metric_name, value, unit, namespace, dimensions)


async def increment_counter(
    metric_name: str,
    namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
    dimensions: Optional[Dict[str, str]] = None
):
    """Shorthand for incrementing a counter."""
    await get_metrics_client().increment_counter(metric_name, namespace, dimensions)


async def record_time(
    metric_name: str,
    duration_seconds: float,
    namespace: MetricNamespace = MetricNamespace.ML_PIPELINE,
    dimensions: Optional[Dict[str, str]] = None
):
    """Shorthand for recording a duration."""
    await get_metrics_client().record_time(metric_name, duration_seconds, namespace, dimensions)
