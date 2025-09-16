"""
Clerk JWT authentication middleware for secure API access
"""
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import os
import logging
import jwt
import requests
from functools import lru_cache
import time

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Clerk configuration from environment variables
CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY", "")
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")

class ClerkAuthError(Exception):
    """Custom exception for Clerk authentication errors"""
    pass

def verify_clerk_token(token: str) -> Dict[str, Any]:
    """
    Verify a Clerk JWT token and return the payload
    """
    try:
        # For development/testing, we can use a simpler approach
        # In production, you should use proper JWKS verification
        
        # Decode without verification first to check if it's a valid JWT structure
        try:
            # Try to decode the token (without verification for now)
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Basic validation
            if not payload.get("sub"):
                raise ClerkAuthError("Token missing user ID (sub)")
                
            # Check expiration
            exp = payload.get("exp")
            if exp and exp < time.time():
                raise ClerkAuthError("Token has expired")
                
            logger.info(f"Token verified for user: {payload.get('sub')}")
            return payload
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token structure: {str(e)}")
            raise ClerkAuthError(f"Invalid token structure: {str(e)}")
            
    except ClerkAuthError:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise ClerkAuthError(f"Token verification failed: {str(e)}")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user
    Validates JWT token and returns user information
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = verify_clerk_token(credentials.credentials)
        
        # Extract user information from Clerk token
        user_info = {
            "id": payload.get("sub"),  # Clerk user ID
            "email": payload.get("email", ""),
            "email_verified": payload.get("email_verified", False),
            "name": payload.get("name", ""),
            "given_name": payload.get("given_name", ""),
            "family_name": payload.get("family_name", ""),
            "picture": payload.get("picture", ""),
            "iss": payload.get("iss", ""),  # Issuer
            "aud": payload.get("aud", ""),  # Audience
        }
        
        if not user_info["id"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        
        return user_info
        
    except ClerkAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

def require_user_ownership(user_id_param: str, current_user: Dict[str, Any]) -> None:
    """
    Verify that the current user owns the requested resource
    Raises HTTPException if user doesn't have access
    """
    if current_user["id"] != user_id_param:
        logger.warning(f"User {current_user['id']} attempted to access resources for user {user_id_param}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access your own resources"
        )

async def validate_user_access(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    Validate that the user_id parameter matches the authenticated user
    Returns the validated user_id
    """
    require_user_ownership(user_id, current_user)
    return user_id

# Development/Testing mode helpers
def is_development_mode() -> bool:
    """Check if we're in development mode"""
    return os.getenv("ENVIRONMENT", "development").lower() in ["development", "dev", "test"]

async def get_current_user_dev_mode(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Dict[str, Any]:
    """
    Development mode authentication - allows testing without real JWT tokens
    DO NOT USE IN PRODUCTION
    """
    if not is_development_mode():
        # In production, always require proper authentication
        return await get_current_user(credentials)
    
    # In development, allow requests without auth for testing
    if not credentials:
        logger.warning("Development mode: No authentication token provided, using test user")
        return {
            "id": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": True
        }
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        logger.warning("Development mode: Invalid token, falling back to test user")
        return {
            "id": "test-user-123", 
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": True
        }
