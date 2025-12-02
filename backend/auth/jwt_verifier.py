"""
Production JWT Verification for Clerk Authentication

This module provides enterprise-grade JWT signature verification for Clerk tokens,
including JWKS caching, graceful degradation, and comprehensive error handling.

Security Features:
- RS256 signature verification with Clerk's public keys
- JWKS caching with 24-hour TTL
- Async-safe locking to prevent concurrent JWKS fetches
- Graceful degradation using stale cache on fetch failures
- Comprehensive claim validation (iss, exp, iat, sub)

Usage:
    verifier = await get_jwt_verifier()
    payload = await verifier.verify_token(token)
"""
import os
import httpx
import asyncio
import time
from typing import Optional, Dict
from jose import jwk, jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


# ========================================================================
# MONITORING METRICS
# ========================================================================

class JWTMetrics:
    """
    In-memory metrics collector for JWT verification
    
    These metrics can be exported to CloudWatch, Prometheus, or other
    monitoring systems for production observability.
    """
    def __init__(self):
        self.verification_success_count = 0
        self.verification_failure_count = 0
        self.jwks_fetch_count = 0
        self.jwks_cache_hit_count = 0
        self.jwks_stale_cache_use_count = 0
        self.last_reset_time = time.time()
    
    def record_verification_success(self):
        """Increment successful verification counter"""
        self.verification_success_count += 1
        logger.debug(f"[METRIC] JWT verifications succeeded: {self.verification_success_count}")
    
    def record_verification_failure(self, reason: str):
        """Increment failed verification counter"""
        self.verification_failure_count += 1
        logger.warning(f"[METRIC] JWT verification failed ({reason}). Total failures: {self.verification_failure_count}")
    
    def record_jwks_fetch(self):
        """Increment JWKS fetch counter"""
        self.jwks_fetch_count += 1
        logger.info(f"[METRIC] JWKS fetched from Clerk. Total fetches: {self.jwks_fetch_count}")
    
    def record_jwks_cache_hit(self):
        """Increment JWKS cache hit counter"""
        self.jwks_cache_hit_count += 1
        logger.debug(f"[METRIC] JWKS cache hit. Total hits: {self.jwks_cache_hit_count}")
    
    def record_jwks_stale_cache_use(self):
        """Increment stale cache usage counter"""
        self.jwks_stale_cache_use_count += 1
        logger.warning(f"[METRIC] Used stale JWKS cache. Total: {self.jwks_stale_cache_use_count}")
    
    def get_stats(self) -> Dict:
        """
        Get current metrics as dictionary
        
        Returns:
            dict: Current metric values
        """
        uptime = time.time() - self.last_reset_time
        return {
            "verification_success_count": self.verification_success_count,
            "verification_failure_count": self.verification_failure_count,
            "verification_success_rate": (
                self.verification_success_count / 
                max(1, self.verification_success_count + self.verification_failure_count)
            ),
            "jwks_fetch_count": self.jwks_fetch_count,
            "jwks_cache_hit_count": self.jwks_cache_hit_count,
            "jwks_cache_hit_rate": (
                self.jwks_cache_hit_count /
                max(1, self.jwks_cache_hit_count + self.jwks_fetch_count)
            ),
            "jwks_stale_cache_use_count": self.jwks_stale_cache_use_count,
            "uptime_seconds": uptime
        }
    
    def reset(self):
        """Reset all counters (useful for testing)"""
        self.verification_success_count = 0
        self.verification_failure_count = 0
        self.jwks_fetch_count = 0
        self.jwks_cache_hit_count = 0
        self.jwks_stale_cache_use_count = 0
        self.last_reset_time = time.time()
        logger.info("[METRIC] All JWT metrics reset")


# Global metrics instance
_metrics = JWTMetrics()


def get_jwt_metrics() -> JWTMetrics:
    """
    Get global JWT metrics instance
    
    Returns:
        JWTMetrics: Singleton metrics instance
    """
    return _metrics


class JWTVerificationError(Exception):
    """Custom exception for JWT verification failures"""
    pass


class ProductionJWTVerifier:
    """
    Production-grade JWT verifier for Clerk authentication
    
    Features:
    - JWKS caching with configurable TTL
    - Async lock to prevent concurrent JWKS fetches (thundering herd protection)
    - Graceful degradation (uses stale cache on fetch failure)
    - Proper RS256 signature verification
    - Comprehensive error logging and monitoring hooks
    """
    
    def __init__(self):
        """
        Initialize JWT verifier with Clerk configuration
        
        Environment Variables Required:
            CLERK_FRONTEND_API: Your Clerk domain (e.g., adapted-tern-12.clerk.accounts.dev)
        
        Raises:
            ValueError: If CLERK_FRONTEND_API is not configured correctly
        """
        # Get Clerk domain from environment
        self.clerk_domain = self._get_clerk_domain()
        
        # Validate domain format (should not include protocol)
        if self.clerk_domain.startswith("http"):
            raise ValueError(
                "CLERK_FRONTEND_API should be domain only "
                "(e.g., 'adapted-tern-12.clerk.accounts.dev'), not a full URL"
            )
        
        # Configure endpoints
        self.jwks_url = f"https://{self.clerk_domain}/.well-known/jwks.json"
        self.issuer = f"https://{self.clerk_domain}"
        
        # JWKS cache configuration
        self.jwks_cache: Optional[Dict] = None
        self.jwks_last_fetched: float = 0
        self.cache_ttl: int = 86400  # 24 hours (JWKS keys rarely change)
        self._lock = asyncio.Lock()
        
        logger.info(
            f"✅ JWT Verifier initialized for Clerk domain: {self.clerk_domain}"
        )
        logger.info(f"   JWKS URL: {self.jwks_url}")
        logger.info(f"   Issuer: {self.issuer}")
    
    def _get_clerk_domain(self) -> str:
        """
        Get Clerk domain from environment with validation
        
        Priority:
        1. CLERK_FRONTEND_API (explicit domain)
        2. Fallback error with helpful message
        
        Returns:
            str: Clerk domain
            
        Raises:
            ValueError: If domain not configured
        """
        # Option 1: Explicit domain (most reliable)
        explicit_domain = os.getenv("CLERK_FRONTEND_API")
        if explicit_domain:
            return explicit_domain.strip()
        
        # Option 2: Try to extract from CLERK_PUBLISHABLE_KEY
        # Note: Clerk keys don't embed domain in a parseable way,
        # so we require explicit configuration
        pub_key = os.getenv("CLERK_PUBLISHABLE_KEY", "")
        if pub_key:
            logger.warning(
                "CLERK_PUBLISHABLE_KEY found but CLERK_FRONTEND_API not set. "
                "Please set CLERK_FRONTEND_API explicitly."
            )
        
        # No valid configuration found
        raise ValueError(
            "CLERK_FRONTEND_API environment variable required.\n\n"
            "To find your Clerk domain:\n"
            "1. Go to https://dashboard.clerk.com\n"
            "2. Select your application\n"
            "3. Go to API Keys section\n"
            "4. Look for 'Frontend API' - copy the domain part\n"
            "   Example: adapted-tern-12.clerk.accounts.dev\n"
            "   OR your custom domain: clerk.yourapp.com\n\n"
            "Then set: CLERK_FRONTEND_API=your-domain-here"
        )
    
    async def get_jwks(self) -> Dict:
        """
        Fetch JWKS from Clerk with caching and async locking
        
        This method implements:
        - Fast path: Return cached JWKS if still valid
        - Slow path: Fetch fresh JWKS with async locking to prevent concurrent fetches
        - Graceful degradation: Use stale cache if fetch fails
        
        Returns:
            dict: JWKS data containing public keys
            
        Raises:
            HTTPException: If JWKS cannot be fetched and no cache available
        """
        current_time = time.time()
        
        # Fast path: return cached JWKS if still valid
        if (self.jwks_cache and 
            (current_time - self.jwks_last_fetched) < self.cache_ttl):
            _metrics.record_jwks_cache_hit()
            return self.jwks_cache
        
        # Slow path: fetch fresh JWKS with locking
        async with self._lock:
            # Double-check cache after acquiring lock (another request may have fetched)
            if (self.jwks_cache and 
                (current_time - self.jwks_last_fetched) < self.cache_ttl):
                return self.jwks_cache
            
            # Fetch JWKS from Clerk
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    logger.info(f"Fetching JWKS from {self.jwks_url}")
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    jwks_data = response.json()
                    
                    # Validate JWKS structure
                    if not isinstance(jwks_data, dict):
                        raise ValueError("JWKS response is not a dictionary")
                    if 'keys' not in jwks_data:
                        raise ValueError("JWKS response missing 'keys' field")
                    if not jwks_data['keys']:
                        raise ValueError("JWKS 'keys' array is empty")
                    
                    # ✅ ENHANCED VALIDATION (from Chat DeepSeek)
                    # Validate each key has required fields
                    for key in jwks_data['keys']:
                        if not key.get('kid'):
                            raise ValueError("JWKS key missing 'kid' (key ID) field")
                        if not key.get('kty'):
                            raise ValueError("JWKS key missing 'kty' (key type) field")
                    
                    # Update cache
                    self.jwks_cache = jwks_data
                    self.jwks_last_fetched = current_time
                    
                    _metrics.record_jwks_fetch()
                    logger.info(
                        f"✅ Successfully fetched JWKS with "
                        f"{len(jwks_data['keys'])} keys"
                    )
                    return jwks_data
                    
            except httpx.TimeoutException:
                logger.error("❌ Timeout fetching JWKS from Clerk")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"❌ HTTP error fetching JWKS: {e.response.status_code}"
                )
            except ValueError as e:
                logger.error(f"❌ Invalid JWKS structure: {str(e)}")
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching JWKS: {str(e)}")
            
            # Graceful degradation: use stale cache if available
            if self.jwks_cache:
                cache_age = current_time - self.jwks_last_fetched
                _metrics.record_jwks_stale_cache_use()
                logger.warning(
                    f"⚠️ Using stale JWKS cache (age: {cache_age:.0f} seconds) "
                    f"due to fetch failure"
                )
                return self.jwks_cache
            
            # No cache available - fail
            logger.critical("❌ No JWKS cache available and fetch failed!")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please try again."
            )
    
    def _find_signing_key(self, jwks: Dict, kid: str) -> Dict:
        """
        Find signing key in JWKS by key ID
        
        Args:
            jwks: JWKS data
            kid: Key ID from JWT header
            
        Returns:
            dict: JWK key data
            
        Raises:
            JWTVerificationError: If key not found
        """
        for key_data in jwks.get('keys', []):
            if key_data.get('kid') == kid:
                return key_data
        
        available_kids = [k.get('kid') for k in jwks.get('keys', [])]
        raise JWTVerificationError(
            f"Signing key not found for kid '{kid}'. "
            f"Available keys: {available_kids}"
        )
    
    async def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token signature and claims
        
        This method:
        1. Validates token structure
        2. Extracts key ID from token header
        3. Fetches appropriate public key from JWKS
        4. Verifies RS256 signature
        5. Validates JWT claims (issuer, expiration, etc.)
        6. Returns decoded payload
        
        Args:
            token: JWT token string
            
        Returns:
            dict: Decoded token payload with validated claims
            
        Raises:
            JWTVerificationError: If token is invalid for any reason
        """
        # ✅ ENHANCED PRE-FLIGHT VALIDATION (from Chat DeepSeek)
        if not token or not isinstance(token, str):
            raise JWTVerificationError("Invalid token format")
        
        token = token.strip()
        
        # Basic structural validation
        if len(token) < 10:
            raise JWTVerificationError("Token too short to be valid JWT")
        
        # JWT should have 3 parts separated by dots (header.payload.signature)
        parts = token.split('.')
        if len(parts) != 3:
            raise JWTVerificationError(
                f"Token structure invalid (expected 3 parts, got {len(parts)})"
            )
        
        try:
            # Step 1: Extract key ID from token header (without verification)
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            
            if not kid:
                raise JWTVerificationError(
                    "Token header missing 'kid' (key ID) field"
                )
            
            # Step 2: Fetch JWKS and find the signing key
            jwks = await self.get_jwks()
            key_data = self._find_signing_key(jwks, kid)
            
            # Step 3: Construct public key from JWK
            try:
                public_key = jwk.construct(key_data)
            except Exception as e:
                raise JWTVerificationError(
                    f"Failed to construct public key from JWKS: {str(e)}"
                )
            
            # Step 4: Verify signature and decode token
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],  # Clerk uses RS256
                issuer=self.issuer,
                options={
                    'verify_signature': True,  # ✅ CRITICAL: Verify signature
                    'verify_iss': True,        # Verify issuer matches Clerk domain
                    'verify_exp': True,        # Verify token not expired
                    'verify_iat': True,        # Verify issued-at time is valid
                    'verify_aud': False,       # Clerk may not include audience
                    'verify_nbf': False,       # Clerk may not include not-before
                    'require_exp': True,       # Require expiration claim
                    'require_iat': True,       # Require issued-at claim
                }
            )
            
            # Step 5: Validate required custom claims
            if not payload.get('sub'):
                raise JWTVerificationError(
                    "Token payload missing 'sub' (subject/user ID) claim"
                )
            
            _metrics.record_verification_success()
            logger.info(
                f"✅ JWT signature verified successfully for user: {payload.get('sub')}"
            )
            return payload
            
        except ExpiredSignatureError:
            _metrics.record_verification_failure("expired")
            logger.warning("Token verification failed: Token has expired")
            raise JWTVerificationError("Token has expired. Please log in again.")
            
        except JWTClaimsError as e:
            _metrics.record_verification_failure("invalid_claims")
            logger.warning(f"Token verification failed: Invalid claims - {str(e)}")
            raise JWTVerificationError(f"Token claims invalid: {str(e)}")
            
        except JWTError as e:
            _metrics.record_verification_failure("jwt_error")
            logger.warning(f"Token verification failed: {str(e)}")
            raise JWTVerificationError(f"Token verification failed: {str(e)}")
            
        except JWTVerificationError:
            # Re-raise our custom exceptions as-is (already counted)
            raise
            
        except Exception as e:
            _metrics.record_verification_failure("unexpected")
            logger.error(
                f"❌ Unexpected error during token verification: {str(e)}",
                exc_info=True
            )
            raise JWTVerificationError("Token verification failed unexpectedly")


# ✅ THREAD-SAFE SINGLETON (corrected from both DeepSeek analyses)
_verifier: Optional[ProductionJWTVerifier] = None
_verifier_lock = asyncio.Lock()


async def get_jwt_verifier() -> ProductionJWTVerifier:
    """
    Get singleton JWT verifier instance
    
    This function implements thread-safe lazy initialization using
    double-checked locking pattern with async lock.
    
    Returns:
        ProductionJWTVerifier: Singleton verifier instance
    """
    global _verifier
    
    # Fast path: return existing verifier
    if _verifier is not None:
        return _verifier
    
    # Slow path: initialize with locking
    async with _verifier_lock:
        # Double-check after acquiring lock
        if _verifier is None:
            _verifier = ProductionJWTVerifier()
    
    return _verifier

