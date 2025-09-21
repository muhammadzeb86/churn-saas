"""
RetainWise Analytics Backend API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import configuration and setup
from backend.core.config import settings
from backend.api.database import init_db

# Import routers
from backend.api.routes import predict, powerbi, upload, waitlist, clerk, uploads_list, predictions

# Import monitoring and health routes
from backend.monitoring.health import router as monitoring_router

# Import middleware
from backend.middleware.rate_limiter import rate_limit_middleware
from backend.middleware.input_validator import input_validation_middleware
from backend.middleware.security_logger import security_logging_middleware
from backend.middleware.error_handler import setup_error_handlers
from backend.monitoring.metrics import setup_monitoring

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RetainWise Analytics API",
    description="AI-powered customer retention analytics platform",
    version="2.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None
)

# Setup global error handlers
setup_error_handlers(app)

# Setup monitoring
setup_monitoring(app)

# Security middleware (applied in reverse order)
app.middleware("http")(security_logging_middleware)
app.middleware("http")(input_validation_middleware)
app.middleware("http")(rate_limit_middleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://retainwiseanalytics.com",
        "https://www.retainwiseanalytics.com",
        "https://app.retainwiseanalytics.com",
        "https://backend.retainwiseanalytics.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(predict.router)      # Prediction routes are at /predict/*
app.include_router(powerbi.router)      # PowerBI routes are at /powerbi/*
app.include_router(upload.router)       # Upload routes are at /upload/*
app.include_router(uploads_list.router) # Upload list routes are at /uploads/*
app.include_router(predictions.router)  # Predictions routes are at /predictions/*
app.include_router(waitlist.router)     # Waitlist routes are at /api/waitlist/*
app.include_router(clerk.router)        # Clerk webhook routes are at /api/clerk/*
app.include_router(monitoring_router)   # Monitoring routes are at /monitoring/*

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
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

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown"""
    logger.info("=== RETAINWISE ANALYTICS BACKEND SHUTDOWN ===")
    # Add any cleanup code here
    logger.info("=== SHUTDOWN COMPLETE ===")

@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse(content={
        "message": "RetainWise Analytics backend is running",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
        "status": "operational"
    })

@app.get("/health")
async def health_check():
    """Basic health check endpoint (kept for ALB compatibility)"""
    return {"status": "healthy", "service": "retainwise-backend"}

# Legacy health endpoint for backward compatibility
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including database connectivity"""
    try:
        from backend.api.health import db_ping_ok
        db_ok = await db_ping_ok()
        if not db_ok:
            raise Exception("Database ping failed")
        
        return {
            "status": "healthy", 
            "service": "retainwise-backend",
            "database": "connected",
            "version": "2.0.0"
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy",
                "service": "retainwise-backend", 
                "database": "disconnected",
                "error": str(e),
                "version": "2.0.0"
            }
        )
