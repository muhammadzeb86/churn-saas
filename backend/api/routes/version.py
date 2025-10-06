"""
Version endpoint for deployment verification
Returns deployed commit SHA and build information
"""

import os
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class VersionInfo(BaseModel):
    """Version information model"""
    service: str
    version: str
    commit_sha: str
    build_time: str
    environment: str
    deployment_id: Optional[str] = None

@router.get("/__version", response_model=VersionInfo)
async def get_version():
    """
    Get deployed version information
    Returns commit SHA and build details for deployment verification
    """
    try:
        # Get commit SHA from environment or git
        commit_sha = os.getenv("GIT_COMMIT_SHA")
        if not commit_sha:
            try:
                # Fallback to git command if available
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                commit_sha = result.stdout.strip() if result.returncode == 0 else "unknown"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                commit_sha = "unknown"
        
        # Get build time from environment or current time
        build_time = os.getenv("BUILD_TIME", datetime.utcnow().isoformat())
        
        # Get deployment ID from environment
        deployment_id = os.getenv("DEPLOYMENT_ID")
        
        return VersionInfo(
            service="retainwise-backend",
            version=os.getenv("APP_VERSION", "1.0.0"),
            commit_sha=commit_sha,
            build_time=build_time,
            environment=os.getenv("ENVIRONMENT", "production"),
            deployment_id=deployment_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve version information: {str(e)}"
        )

@router.get("/__health/version")
async def health_check_version():
    """
    Health check endpoint that includes version information
    Used by deployment verification
    """
    try:
        version_info = await get_version()
        return {
            "status": "healthy",
            "version": version_info.version,
            "commit_sha": version_info.commit_sha,
            "environment": version_info.environment,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
