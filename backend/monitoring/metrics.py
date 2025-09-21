"""
Application monitoring and metrics collection
"""
import time
import logging
from typing import Dict, Any
from fastapi import Request
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ApplicationMetrics:
    """Collect and track application metrics"""
    
    def __init__(self):
        self.request_count = defaultdict(int)
        self.response_times = defaultdict(deque)
        self.error_count = defaultdict(int)
        self.active_requests = 0
        self.start_time = datetime.now()
        
        # Keep only last 100 response times per endpoint
        self.max_response_times = 100
    
    def record_request(self, method: str, path: str, response_time: float, status_code: int):
        """Record request metrics"""
        endpoint = f"{method} {path}"
        
        # Count requests
        self.request_count[endpoint] += 1
        self.request_count["_total"] += 1
        
        # Track response times
        if len(self.response_times[endpoint]) >= self.max_response_times:
            self.response_times[endpoint].popleft()
        self.response_times[endpoint].append(response_time)
        
        # Count errors
        if status_code >= 400:
            self.error_count[endpoint] += 1
            self.error_count["_total"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        uptime = datetime.now() - self.start_time
        
        # Calculate average response times
        avg_response_times = {}
        for endpoint, times in self.response_times.items():
            if times:
                avg_response_times[endpoint] = sum(times) / len(times)
        
        return {
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_formatted": str(uptime).split(".")[0],
            "active_requests": self.active_requests,
            "total_requests": self.request_count.get("_total", 0),
            "total_errors": self.error_count.get("_total", 0),
            "error_rate": (
                self.error_count.get("_total", 0) / max(self.request_count.get("_total", 1), 1) * 100
            ),
            "request_count_by_endpoint": dict(self.request_count),
            "error_count_by_endpoint": dict(self.error_count),
            "avg_response_time_by_endpoint": avg_response_times
        }

# Global metrics instance
app_metrics = ApplicationMetrics()

class HealthChecker:
    """Application health checking"""
    
    @staticmethod
    async def check_database() -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            from backend.api.health import db_ping_ok
            is_healthy = await db_ping_ok()
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": 0  # Could add timing here
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    async def check_sqs() -> Dict[str, Any]:
        """Check SQS connectivity"""
        try:
            from backend.core.config import settings
            if not settings.PREDICTIONS_QUEUE_URL:
                return {"status": "disabled", "reason": "No SQS queue configured"}
            
            sqs_client = settings.get_boto3_sqs()
            sqs_client.get_queue_attributes(
                QueueUrl=settings.PREDICTIONS_QUEUE_URL,
                AttributeNames=["QueueArn"]
            )
            return {"status": "healthy"}
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    async def check_s3() -> Dict[str, Any]:
        """Check S3 connectivity"""
        try:
            from backend.core.config import settings
            s3_client = settings.get_boto3_s3()
            s3_client.head_bucket(Bucket=settings.S3_BUCKET)
            return {"status": "healthy"}
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e)
            }

async def monitoring_middleware(request: Request, call_next):
    """Middleware to collect request metrics"""
    start_time = time.time()
    app_metrics.active_requests += 1
    
    try:
        response = await call_next(request)
        response_time = time.time() - start_time
        
        # Record metrics
        app_metrics.record_request(
            method=request.method,
            path=request.url.path,
            response_time=response_time,
            status_code=response.status_code
        )
        
        return response
    finally:
        app_metrics.active_requests -= 1

def setup_monitoring(app):
    """Set up monitoring middleware"""
    app.middleware("http")(monitoring_middleware)
    logger.info("Monitoring middleware configured")
