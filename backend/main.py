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
from backend.monitoring.metrics import monitoring_middleware

# Import API routes
from backend.api.routes import predict, powerbi, upload, waitlist, clerk, uploads_list, predictions, version
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
    
    logger.info("=== STARTUP COMPLETE ===")
    
    yield
    
    # Shutdown
    logger.info("=== RETAINWISE ANALYTICS BACKEND SHUTDOWN ===")
    # Add any cleanup code here
    logger.info("=== SHUTDOWN COMPLETE ===")

# Create FastAPI application with lifespan
app = FastAPI(
    title="RetainWise Analytics API",
    description="Production-ready customer retention analytics with ML-powered churn prediction",
    version="2.0.0",
    lifespan=lifespan
)

# Error handler middleware (must be first to catch all exceptions)
app.middleware("http")(error_handler_middleware)

# Security middleware (order matters - these run in reverse order)
app.middleware("http")(monitoring_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(input_validation_middleware)
app.middleware("http")(security_logging_middleware)

# Setup global error handlers
setup_error_handlers(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://retainwiseanalytics.com",
        "https://www.retainwiseanalytics.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(predict.router, prefix="/api", tags=["predictions"])
app.include_router(powerbi.router, prefix="/api", tags=["powerbi"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(uploads_list.router, prefix="/api", tags=["uploads"])
app.include_router(predictions.router, prefix="/api", tags=["predictions"])
app.include_router(waitlist.router, prefix="/api", tags=["waitlist"])
app.include_router(clerk.router, prefix="/api", tags=["auth"])
app.include_router(version.router, tags=["version"])
app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])

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


