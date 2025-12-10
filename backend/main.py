"""
RetainWise Analytics Backend API

A production-ready FastAPI application for customer retention analytics
with ML-powered churn prediction, secure authentication, and comprehensive monitoring.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import configuration and database
from backend.core.config import settings
from backend.api.database import init_db

# Import middleware
from backend.middleware.rate_limiter import rate_limit_middleware
from backend.middleware.input_validator import input_validation_middleware
from backend.middleware.security_logger import security_logging_middleware
from backend.middleware.error_handler import setup_error_handlers, error_handler_middleware

# Import API routes
from backend.api.routes import predict, upload, waitlist, clerk, uploads_list, predictions, version, auth_metrics, csv_mapper
from backend.monitoring.health import router as monitoring_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("=== RETAINWISE ANALYTICS BACKEND STARTUP ===")
    
    # Log configuration
    settings.log_config()
    
    # ✅ NEW: Initialize CloudWatch metrics client
    try:
        from backend.monitoring.metrics import get_metrics_client
        metrics = get_metrics_client()
        await metrics.start()
        logger.info("CloudWatch metrics client started successfully")
    except Exception as e:
        logger.error(f"Metrics client initialization failed: {e}")
        logger.warning("Metrics will not be published, but application will continue")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("Application will continue running, but database operations may fail")
    
    # Test SQS connection in production (if configured)
    if settings.ENVIRONMENT == "production" and settings.PREDICTIONS_QUEUE_URL:
        try:
            sqs_client = settings.get_boto3_sqs()
            # Test connection by getting queue attributes
            sqs_client.get_queue_attributes(
                QueueUrl=settings.PREDICTIONS_QUEUE_URL,
                AttributeNames=["QueueArn"]
            )
            logger.info("SQS connection verified successfully")
        except Exception as e:
            logger.error(f"SQS connection failed: {e}")
            logger.warning("Prediction processing may not work properly")
    elif settings.ENVIRONMENT == "production":
        logger.info("SQS not configured - prediction processing disabled")
    
    # ✅ NEW: Run authentication system self-test
    try:
        from backend.auth.middleware import startup_auth_check
        await startup_auth_check()
    except Exception as e:
        logger.error(f"Authentication system self-test failed: {e}")
        logger.warning("Authentication may not work properly")
    
    logger.info("=== STARTUP COMPLETE ===")
    
    yield
    
    # Shutdown
    logger.info("=== RETAINWISE ANALYTICS BACKEND SHUTDOWN ===")
    
    # ✅ NEW: Gracefully shutdown metrics client (flush remaining metrics)
    try:
        from backend.monitoring.metrics import get_metrics_client
        metrics = get_metrics_client()
        await metrics.stop()
        logger.info("CloudWatch metrics client stopped successfully")
    except Exception as e:
        logger.error(f"Metrics client shutdown failed: {e}")
    
    logger.info("=== SHUTDOWN COMPLETE ===")

# Create FastAPI application with lifespan
app = FastAPI(
    title="RetainWise Analytics API",
    description="Production-ready customer retention analytics with ML-powered churn prediction",
    version="2.0.1",  # Deployment: Nov 1, 2025 - CORS middleware order fix
    lifespan=lifespan
)

# ✅ CRITICAL: CORS MUST BE ADDED FIRST
# FastAPI middleware runs in REVERSE order - first added runs last (outermost layer)
# CORS must wrap ALL other middleware to ensure headers are added to ALL responses
#
# IMPORTANT: When allow_credentials=True, wildcards are converted to explicit lists
# by FastAPI internally. Using explicit lists for maximum browser compatibility.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.retainwiseanalytics.com",  # Primary frontend
        "http://localhost:3000",                 # Local development
        "https://retainwiseanalytics.com",       # Root domain
        "https://www.retainwiseanalytics.com",   # WWW variant
    ],
    allow_credentials=True,
    # Explicit methods for maximum compatibility with multipart/form-data
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    # Explicit headers - critical for file uploads and JWT authentication
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Type",      # Critical for multipart/form-data uploads
        "Content-Length",
        "Authorization",     # Critical for JWT authentication
        "X-Requested-With",
        "X-Request-ID",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "Referer",
    ],
    expose_headers=["Content-Length", "Content-Type", "Content-Disposition", "X-Request-ID"],
    max_age=3600,  # Cache preflight for 1 hour
)

# Error handler middleware (must be early to catch all exceptions)
app.middleware("http")(error_handler_middleware)

# Security middleware (order matters - these run in reverse order)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(input_validation_middleware)
app.middleware("http")(security_logging_middleware)

# Setup global error handlers
setup_error_handlers(app)

# Include API routes
app.include_router(predict.router, prefix="/api", tags=["predictions"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(uploads_list.router, prefix="/api", tags=["uploads"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(waitlist.router, prefix="/api", tags=["waitlist"])
app.include_router(clerk.router, prefix="/api", tags=["auth"])
app.include_router(auth_metrics.router, prefix="/api", tags=["auth"])
app.include_router(version.router, tags=["version"])
app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
app.include_router(csv_mapper.router, tags=["csv-mapping"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RetainWise Analytics backend is running",
        "version": "2.0.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "retainwise-backend",
        "timestamp": "2024-01-01T00:00:00Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )


