"""
Authentication Middleware for FastAPI

Provides JWT authentication with support for both development and production modes:
- Development mode (AUTH_DEV_MODE=true): Validates token structure only
- Production mode (AUTH_DEV_MODE=false): Full JWT signature verification with Clerk JWKS

This module also supports phased rollout via feature flag:
- JWT_SIGNATURE_VERIFICATION_ENABLED controls whether signature verification is active
"""
import os
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# Security scheme for FastAPI OpenAPI docs
security = HTTPBearer(
    scheme_name="JWT Bearer Token",
    description="Enter your Clerk JWT token from the Authorization header"
)

# Configuration from environment
AUTH_DEV_MODE = os.getenv("AUTH_DEV_MODE", "false").lower() in ["true", "1", "yes"]

# ✅ FEATURE FLAG for phased rollout (safe deployment strategy)
JWT_SIGNATURE_VERIFICATION_ENABLED = os.getenv(
    "JWT_SIGNATURE_VERIFICATION_ENABLED",
    "false"  # Default to FALSE initially for safe rollout
).lower() in ["true", "1", "yes"]

# Log authentication mode on startup
if AUTH_DEV_MODE:
    logger.warning(
        "⚠️  AUTH_DEV_MODE is ENABLED - JWT signature verification is DISABLED.\n"
        "   This should ONLY be used in local development!\n"
        "   Set AUTH_DEV_MODE=false in production."
    )
else:
    if JWT_SIGNATURE_VERIFICATION_ENABLED:
        logger.info(
            "✅ Production authentication mode ACTIVE:\n"
            "   - JWT signature verification: ENABLED\n"
            "   - JWKS validation: ENABLED\n"
            "   - Security: MAXIMUM"
        )
    else:
        logger.warning(
            "⚠️  Production mode but signature verification is DISABLED:\n"
            "   - JWT_SIGNATURE_VERIFICATION_ENABLED=false\n"
            "   - Using fallback authentication (structure check only)\n"
            "   - Set JWT_SIGNATURE_VERIFICATION_ENABLED=true to enable full security"
        )


# ✅ STARTUP VALIDATION (from Chat DeepSeek)
def validate_auth_configuration():
    """
    Validate authentication configuration on startup
    
    This function checks that all required environment variables are set
    and logs warnings for potentially insecure configurations.
    """
    if not AUTH_DEV_MODE and not JWT_SIGNATURE_VERIFICATION_ENABLED:
        logger.warning(
            "⚠️  SECURITY WARNING: Production mode without signature verification!\n"
            "   Current configuration:\n"
            "   - AUTH_DEV_MODE=false\n"
            "   - JWT_SIGNATURE_VERIFICATION_ENABLED=false\n"
            "   This means tokens are only structure-checked, NOT cryptographically verified.\n"
            "   Set JWT_SIGNATURE_VERIFICATION_ENABLED=true to enable full security."
        )
    
    if JWT_SIGNATURE_VERIFICATION_ENABLED and not os.getenv("CLERK_FRONTEND_API"):
        logger.error(
            "❌ CONFIGURATION ERROR:\n"
            "   JWT_SIGNATURE_VERIFICATION_ENABLED=true but CLERK_FRONTEND_API not set!\n"
            "   Production authentication will FAIL.\n"
            "   Set CLERK_FRONTEND_API to your Clerk domain."
        )


# Run validation on module import
validate_auth_configuration()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    FastAPI dependency for JWT authentication
    
    This function implements a three-tier authentication strategy:
    1. Development mode: Structure validation only (AUTH_DEV_MODE=true)
    2. Production with feature flag: Full signature verification (JWT_SIGNATURE_VERIFICATION_ENABLED=true)
    3. Production fallback: Structure validation (JWT_SIGNATURE_VERIFICATION_ENABLED=false)
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        
    Returns:
        dict: User information extracted from JWT:
            - id: User ID (from 'sub' claim)
            - email: User email
            - email_verified: Email verification status
            - name: Full name
            - first_name: First name
            - last_name: Last name
            - picture: Avatar URL
            - dev_mode: Boolean indicating if dev mode was used
            - raw_payload: Complete JWT payload
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # === TIER 1: DEVELOPMENT MODE ===
    if AUTH_DEV_MODE:
        return await _authenticate_dev_mode(token)
    
    # === TIER 2: PRODUCTION WITH SIGNATURE VERIFICATION ===
    if JWT_SIGNATURE_VERIFICATION_ENABLED:
        return await _authenticate_production_verified(token)
    
    # === TIER 3: PRODUCTION FALLBACK (structure check only) ===
    return await _authenticate_production_fallback(token)


async def _authenticate_dev_mode(token: str) -> Dict:
    """
    Development mode authentication - structure validation only
    
    WARNING: Does NOT verify JWT signature!
    Only validates token structure and required claims.
    """
    try:
        import jwt as pyjwt
        
        # Decode without signature verification (dev only!)
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        # Validate basic structure
        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID (sub claim)"
            )
        
        logger.debug(
            f"🔓 DEV MODE: Authenticated user {user_id} "
            f"(signature verification SKIPPED)"
        )
        
        return {
            "id": user_id,
            "email": payload.get('email', ''),
            "email_verified": payload.get('email_verified', False),
            "name": payload.get('name', ''),
            "first_name": payload.get('given_name', ''),
            "last_name": payload.get('family_name', ''),
            "picture": payload.get('picture', ''),
            "dev_mode": True,
            "raw_payload": payload
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dev mode authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token structure: {str(e)}"
        )


async def _authenticate_production_verified(token: str) -> Dict:
    """
    Production authentication with full JWT signature verification
    
    This function:
    1. Imports JWT verifier (lazy import)
    2. Verifies JWT signature using Clerk's JWKS
    3. Validates all claims
    4. Returns user information
    """
    try:
        from .jwt_verifier import get_jwt_verifier, JWTVerificationError
        
        # Get verifier instance (singleton)
        verifier = await get_jwt_verifier()
        
        # Verify token with full signature checking
        payload = await verifier.verify_token(token)
        
        logger.info(
            f"✅ Production authentication successful for user {payload.get('sub')} "
            f"(signature VERIFIED)"
        )
        
        return {
            "id": payload.get('sub'),
            "email": payload.get('email', ''),
            "email_verified": payload.get('email_verified', False),
            "name": payload.get('name', ''),
            "first_name": payload.get('given_name', ''),
            "last_name": payload.get('family_name', ''),
            "picture": payload.get('picture', ''),
            "dev_mode": False,
            "signature_verified": True,
            "raw_payload": payload
        }
        
    except JWTVerificationError as e:
        logger.warning(f"⚠️ JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ImportError as e:
        logger.error(f"❌ Failed to import JWT verifier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service configuration error"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected authentication error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def _authenticate_production_fallback(token: str) -> Dict:
    """
    Production fallback authentication - structure validation only
    
    WARNING: This is a FALLBACK mode for safe rollout.
    Does NOT verify JWT signature!
    Should only be used temporarily during deployment.
    """
    try:
        import jwt as pyjwt
        
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID (sub claim)"
            )
        
        logger.warning(
            f"⚠️ FALLBACK: Authenticated user {user_id} via structure check only. "
            f"Signature NOT verified! Enable JWT_SIGNATURE_VERIFICATION_ENABLED=true"
        )
        
        return {
            "id": user_id,
            "email": payload.get('email', ''),
            "email_verified": payload.get('email_verified', False),
            "name": payload.get('name', ''),
            "first_name": payload.get('given_name', ''),
            "last_name": payload.get('family_name', ''),
            "picture": payload.get('picture', ''),
            "dev_mode": False,
            "signature_verified": False,  # ⚠️ NOT VERIFIED
            "raw_payload": payload
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Fallback authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[Dict]:
    """
    Optional authentication - returns user if token is valid, None otherwise
    
    Useful for endpoints that work for both authenticated and unauthenticated users.
    
    Args:
        credentials: Optional HTTP Authorization header
        
    Returns:
        dict: User information if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_user_ownership(resource_user_id: str, current_user: Dict) -> None:
    """
    Verify that the current user owns the resource
    
    This function implements authorization (not authentication).
    Call this after get_current_user() to ensure the authenticated user
    has permission to access a specific resource.
    
    Args:
        resource_user_id: User ID that owns the resource
        current_user: Current authenticated user (from get_current_user)
        
    Raises:
        HTTPException: 403 if user doesn't own the resource
        
    Example:
        @router.get("/predictions/{prediction_id}")
        async def get_prediction(
            prediction_id: str,
            current_user: Dict = Depends(get_current_user),
            db: AsyncSession = Depends(get_db)
        ):
            prediction = await db.get(Prediction, prediction_id)
            require_user_ownership(prediction.user_id, current_user)
            return prediction
    """
    if current_user.get("id") != resource_user_id:
        logger.warning(
            f"⚠️ Authorization failed: user {current_user.get('id')} "
            f"attempted to access resource owned by {resource_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )


# ===== BACKWARD COMPATIBILITY =====

async def get_current_user_dev_mode(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    DEPRECATED: Use get_current_user instead
    
    This function now delegates to get_current_user which respects
    the AUTH_DEV_MODE environment variable.
    
    Maintained for backward compatibility with existing routes.
    """
    logger.warning(
        "get_current_user_dev_mode() is DEPRECATED. Use get_current_user() instead. "
        "Dev mode is now controlled by AUTH_DEV_MODE environment variable."
    )
    return await get_current_user(credentials)


# ===== STARTUP SELF-TEST =====

async def startup_auth_check():
    """
    Run authentication self-test on application startup
    
    This function:
    1. Validates environment configuration
    2. Tests JWT verifier initialization
    3. Tests JWKS fetch
    4. Logs results
    
    Call this from FastAPI's lifespan or startup event.
    """
    logger.info("🔍 Running authentication system self-test...")
    
    if AUTH_DEV_MODE:
        logger.warning("⚠️ AUTH_DEV_MODE enabled - skipping production checks")
        return
    
    if not JWT_SIGNATURE_VERIFICATION_ENABLED:
        logger.warning(
            "⚠️ JWT signature verification disabled - skipping verifier checks"
        )
        return
    
    try:
        # Test 1: Import JWT verifier
        from .jwt_verifier import get_jwt_verifier
        logger.info("✅ JWT verifier module imported successfully")
        
        # Test 2: Initialize verifier
        verifier = await get_jwt_verifier()
        logger.info(f"✅ JWT verifier initialized for domain: {verifier.clerk_domain}")
        
        # Test 3: Fetch JWKS
        jwks = await verifier.get_jwks()
        num_keys = len(jwks.get('keys', []))
        logger.info(f"✅ JWKS fetched successfully: {num_keys} keys available")
        
        logger.info("✅ Authentication system self-test PASSED")
        
    except Exception as e:
        logger.error(
            f"❌ Authentication system self-test FAILED: {str(e)}\n"
            f"   Production authentication may not work correctly!",
            exc_info=True
        )
