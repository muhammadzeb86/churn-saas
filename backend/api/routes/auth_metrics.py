"""
Authentication Metrics API Endpoint
====================================

Exposes JWT verification metrics for monitoring and observability.
These metrics can be consumed by:
- CloudWatch (via custom script)
- Prometheus (via /metrics endpoint)
- DataDog
- Application dashboards

Example response:
{
    "verification_success_count": 1523,
    "verification_failure_count": 12,
    "verification_success_rate": 0.992,
    "jwks_fetch_count": 3,
    "jwks_cache_hit_count": 1520,
    "jwks_cache_hit_rate": 0.998,
    "jwks_stale_cache_use_count": 0,
    "uptime_seconds": 86400
}
"""
from fastapi import APIRouter, Depends
from typing import Dict
from backend.auth.jwt_verifier import get_jwt_metrics
from backend.auth.middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/metrics")
async def get_auth_metrics(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """
    Get JWT authentication metrics
    
    **Authentication Required:** Yes (Bearer token)
    
    **Authorization:** Any authenticated user can view metrics
    
    **Returns:**
    - `verification_success_count`: Total successful verifications
    - `verification_failure_count`: Total failed verifications
    - `verification_success_rate`: Success rate (0.0 to 1.0)
    - `jwks_fetch_count`: Number of JWKS fetches from Clerk
    - `jwks_cache_hit_count`: Number of JWKS cache hits
    - `jwks_cache_hit_rate`: Cache hit rate (0.0 to 1.0)
    - `jwks_stale_cache_use_count`: Times stale cache was used
    - `uptime_seconds`: Metrics collection uptime
    
    **Example:**
    ```
    GET /auth/metrics
    Authorization: Bearer <your_jwt_token>
    
    Response:
    {
        "verification_success_count": 1523,
        "verification_failure_count": 12,
        "verification_success_rate": 0.992,
        ...
    }
    ```
    """
    metrics = get_jwt_metrics()
    return metrics.get_stats()


@router.post("/metrics/reset")
async def reset_auth_metrics(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """
    Reset JWT authentication metrics
    
    **Authentication Required:** Yes (Bearer token)
    
    **Authorization:** Any authenticated user (consider restricting to admins in production)
    
    **Returns:**
    - `status`: "reset"
    - `message`: Confirmation message
    
    **Note:** This endpoint should ideally be restricted to admin users only
    in production. Add role-based access control (RBAC) if needed.
    """
    metrics = get_jwt_metrics()
    metrics.reset()
    
    return {
        "status": "reset",
        "message": "Authentication metrics have been reset successfully"
    }

