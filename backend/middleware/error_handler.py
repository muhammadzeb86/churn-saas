"""
Global error handling for FastAPI application
"""
import logging
import uuid
from fastapi import Request, HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
from typing import Union

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling for the application"""
    
    @staticmethod
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors (422)"""
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Validation error",
                "details": exc.errors(),
                "message": "Invalid request data"
            }
        )
    
    @staticmethod
    async def http_exception_handler(request: Request, exc: Union[FastAPIHTTPException, StarletteHTTPException]):
        """Handle HTTP exceptions (4xx, 5xx)"""
        status_code = exc.status_code
        detail = exc.detail
        
        # Log based on error type
        if status_code >= 500:
            logger.error(f"Server error on {request.method} {request.url.path}: {detail}")
        elif status_code >= 400:
            logger.warning(f"Client error on {request.method} {request.url.path}: {detail}")
        
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": detail,
                "status_code": status_code
            }
        )
    
    @staticmethod
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions (500)"""
        error_id = f"ERR-{hash(str(exc)) % 10000:04d}"
        
        logger.error(
            f"Unhandled exception [{error_id}] on {request.method} {request.url.path}: {str(exc)}",
            extra={
                "error_id": error_id,
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host,
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "error_id": error_id,
                "message": "An unexpected error occurred. Please contact support if the issue persists."
            }
        )

async def error_handler_middleware(request: Request, call_next):
    """Error handler middleware to catch HTTPException"""
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    try:
        return await call_next(request)
    except FastAPIHTTPException as he:
        logger.exception("http_exception", extra={"correlation_id": correlation_id, "path": str(request.url)})
        return JSONResponse(
            status_code=he.status_code,
            content={
                "success": False,
                "error": "http_exception",
                "message": he.detail if hasattr(he, "detail") else "HTTP error",
                "correlation_id": correlation_id,
            },
        )
    except RequestValidationError as ve:
        logger.exception("validation_error", extra={"correlation_id": correlation_id, "path": str(request.url)})
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "validation_error",
                "message": "Invalid request data",
                "correlation_id": correlation_id,
            },
        )
    except Exception as e:
        error_id = f"ERR-{hash(str(e)) % 10000:04d}"
        logger.exception("unhandled_exception", extra={"correlation_id": correlation_id, "error_id": error_id, "path": str(request.url)})
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "error_id": error_id,
                "correlation_id": correlation_id,
            },
        )

def setup_error_handlers(app):
    """Set up global error handlers for the FastAPI app"""
    app.add_exception_handler(RequestValidationError, ErrorHandler.validation_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, ErrorHandler.http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, ErrorHandler.http_exception_handler)
    app.add_exception_handler(Exception, ErrorHandler.general_exception_handler)
    
    logger.info("Global error handlers configured")
