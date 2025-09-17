"""
Security logging middleware for FastAPI
"""
from fastapi import Request
import time
import logging

logger = logging.getLogger(__name__)

class SecurityLogger:
    """Enhanced security logging"""
    
    @staticmethod
    def log_request(request: Request, response_time: float, status_code: int):
        """Log request with security context"""
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")
        method = request.method
        path = request.url.path
        query = str(request.query_params)
        
        # Security-sensitive endpoints
        sensitive_endpoints = ["/predictions", "/uploads", "/download", "/admin"]
        is_sensitive = any(endpoint in path for endpoint in sensitive_endpoints)
        
        # Log level based on sensitivity and status
        if status_code >= 400:
            log_level = logging.WARNING
        elif is_sensitive:
            log_level = logging.INFO
        else:
            log_level = logging.DEBUG
        
        logger.log(
            log_level,
            f"Security Event: {method} {path} - IP: {client_ip} - Status: {status_code} - Time: {response_time:.3f}s"
        )
    
    @staticmethod
    def log_auth_event(event_type: str, user_id: str, client_ip: str, details: str = ""):
        """Log authentication events"""
        logger.warning(
            f"Auth Event: {event_type} - User: {user_id} - IP: {client_ip} - Details: {details}"
        )
    
    @staticmethod
    def log_security_threat(threat_type: str, client_ip: str, details: str):
        """Log security threats"""
        logger.error(
            f"Security Threat: {threat_type} - IP: {client_ip} - Details: {details}"
        )

async def security_logging_middleware(request: Request, call_next):
    """Security logging middleware"""
    start_time = time.time()
    
    response = await call_next(request)
    
    response_time = time.time() - start_time
    SecurityLogger.log_request(request, response_time, response.status_code)
    
    return response 