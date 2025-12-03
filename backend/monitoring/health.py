"""
Health check endpoints for monitoring service status
"""
from fastapi import APIRouter
from typing import Dict, Any
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitoring"])

# Track service start time for uptime calculation
_service_start_time = time.time()

@router.get("/health")
async def basic_health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "retainwise-backend",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check - basic version without old metrics system"""
    uptime_seconds = time.time() - _service_start_time
    
    health_status = {
        "service": "retainwise-backend",
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health_status

@router.get("/metrics")
async def get_metrics():
    """Get basic application metrics"""
    uptime_seconds = time.time() - _service_start_time
    
    return {
        "service": "retainwise-backend",
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Detailed metrics available in CloudWatch"
    }

@router.get("/status")
async def get_system_status():
    """Get overall system status summary"""
    uptime_seconds = time.time() - _service_start_time
    
    # Simple status based on uptime
    if uptime_seconds < 60:  # Less than 1 minute uptime
        status = "starting"
    else:
        status = "operational"
    
    return {
        "status": status,
        "uptime": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.utcnow().isoformat()
    }
