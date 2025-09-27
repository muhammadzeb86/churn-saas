"""
Input validation middleware for FastAPI
"""
from fastapi import Request
from fastapi.responses import JSONResponse
import re
import logging

logger = logging.getLogger(__name__)

class InputValidator:
    """Input validation for security threats"""
    
    # SQL injection patterns
    SQL_PATTERNS = [
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b",
        r"\b(OR|AND)\s+\d+\s*=\s*\d+",
        r"['\"];.*--",
        r"['\"].*\bOR\b.*['\"]",
    ]
    
    # XSS patterns  
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ]
    
    @classmethod
    def validate_input(cls, value: str) -> bool:
        """Validate input for security threats"""
        if not isinstance(value, str):
            return True
        
        # Check for SQL injection
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"SQL injection attempt detected: {value[:100]}")
                return False
        
        # Check for XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"XSS attempt detected: {value[:100]}")
                return False
        
        return True

async def input_validation_middleware(request: Request, call_next):
    """Input validation middleware"""
    # Validate query parameters
    for key, value in request.query_params.items():
        if not InputValidator.validate_input(str(value)):
            logger.warning(f"SQL injection attempt detected: {value[:100]}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "bad_request",
                    "message": "Invalid input detected.",
                },
            )
    
    # Validate path parameters
    for key, value in request.path_params.items():
        if not InputValidator.validate_input(str(value)):
            logger.warning(f"XSS attempt detected: {value[:100]}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "bad_request",
                    "message": "Invalid input detected.",
                },
            )
    
    response = await call_next(request)
    return response
