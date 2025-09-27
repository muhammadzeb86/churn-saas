"""
Enhanced health check endpoints with comprehensive monitoring
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging
from backend.monitoring.metrics import app_metrics, HealthChecker

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitoring"])

@router.get("/health")
async def basic_health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "service": "retainwise-backend"}

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with all dependencies"""
    health_status = {
        "service": "retainwise-backend",
        "status": "healthy",
        "checks": {}
    }
    
    overall_healthy = True
    
    # Check database
    db_health = await HealthChecker.check_database()
    health_status["checks"]["database"] = db_health
    if db_health["status"] != "healthy":
        overall_healthy = False
    
    # Check SQS
    sqs_health = await HealthChecker.check_sqs()
    health_status["checks"]["sqs"] = sqs_health
    if sqs_health["status"] not in ["healthy", "disabled"]:
        overall_healthy = False
    
    # Check S3
    s3_health = await HealthChecker.check_s3()
    health_status["checks"]["s3"] = s3_health
    if s3_health["status"] != "healthy":
        overall_healthy = False
    
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    if not overall_healthy:
        logger.warning("Health check failed", extra={"health_status": health_status})
    
    return health_status

@router.get("/metrics")
async def get_metrics():
    """Get application metrics"""
    return app_metrics.get_metrics()

@router.get("/metrics/detailed")
async def get_detailed_metrics():
    """Get detailed application metrics with health checks"""
    metrics = app_metrics.get_metrics()
    
    # Add health check results
    health_checks = {
        "database": await HealthChecker.check_database(),
        "sqs": await HealthChecker.check_sqs(),
        "s3": await HealthChecker.check_s3()
    }
    
    return {
        "metrics": metrics,
        "health_checks": health_checks,
        "timestamp": metrics.get("uptime_formatted")
    }

@router.get("/status")
async def get_system_status():
    """Get overall system status summary"""
    metrics = app_metrics.get_metrics()
    
    # Determine system health based on error rate and uptime
    error_rate = metrics.get("error_rate", 0)
    uptime_seconds = metrics.get("uptime_seconds", 0)
    
    if error_rate > 10:  # More than 10% errors
        status = "degraded"
    elif error_rate > 5:  # More than 5% errors
        status = "warning"
    elif uptime_seconds < 60:  # Less than 1 minute uptime
        status = "starting"
    else:
        status = "operational"
    
    return {
        "status": status,
        "error_rate": error_rate,
        "uptime": metrics.get("uptime_formatted"),
        "total_requests": metrics.get("total_requests", 0),
        "active_requests": metrics.get("active_requests", 0)
    }
