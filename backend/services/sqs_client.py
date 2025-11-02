"""
SQS Client Management
=====================
Production-grade SQS client with dependency injection.

Features:
- Proper lifecycle management
- Connection pooling
- Error handling
- Thread-safe operations
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from backend.core.config import settings
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class SQSClient:
    """
    Production SQS client with proper resource management
    
    Features:
    - Connection pooling (50 connections)
    - Automatic retries (3 attempts)
    - Thread-safe operations
    - Proper cleanup
    """
    
    def __init__(self):
        self._client: Optional[boto3.client] = None
        self._initialized = False
    
    def initialize(self):
        """
        Initialize SQS client with production settings
        
        Called once at application startup
        """
        if self._initialized:
            return
        
        if not settings.is_sqs_enabled:
            logger.warning("SQS disabled - client not initialized")
            return
        
        try:
            # Production-grade client configuration
            client_config = Config(
                region_name=settings.AWS_REGION,
                retries={
                    'max_attempts': 3,
                    'mode': 'standard'
                },
                max_pool_connections=50,  # Handle concurrent requests
                connect_timeout=5,
                read_timeout=60
            )
            
            self._client = boto3.client('sqs', config=client_config)
            self._initialized = True
            
            logger.info(
                f"✅ SQS client initialized: region={settings.AWS_REGION}, "
                f"queue={settings.sqs_queue_name}"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize SQS client: {str(e)}", exc_info=True)
            self._client = None
            self._initialized = False
    
    def get_client(self) -> Optional[boto3.client]:
        """
        Get SQS client instance
        
        Returns:
            boto3 SQS client or None if not initialized
        """
        if not self._initialized:
            self.initialize()
        return self._client
    
    def close(self):
        """
        Close SQS client and cleanup resources
        
        Called at application shutdown
        """
        if self._client:
            try:
                self._client.close()
                logger.info("✅ SQS client closed")
            except Exception as e:
                logger.error(f"Error closing SQS client: {str(e)}")
            finally:
                self._client = None
                self._initialized = False


# Global SQS client instance (initialized at startup)
sqs_client = SQSClient()


# =====================================================
# DEPENDENCY INJECTION FOR FASTAPI
# =====================================================

async def get_sqs_client() -> Optional[boto3.client]:
    """
    FastAPI dependency for SQS client
    
    Usage:
        @router.post("/upload")
        async def upload(sqs = Depends(get_sqs_client)):
            if sqs:
                sqs.send_message(...)
    
    Returns:
        boto3 SQS client or None if disabled
    """
    client = sqs_client.get_client()
    
    if not client:
        logger.warning("SQS client requested but not available")
    
    return client


# =====================================================
# LIFECYCLE HOOKS FOR FASTAPI
# =====================================================

async def startup_sqs():
    """
    Application startup hook
    
    Add to FastAPI:
        @app.on_event("startup")
        async def startup():
            await startup_sqs()
    """
    logger.info("🚀 Initializing SQS client...")
    sqs_client.initialize()
    
    if settings.is_sqs_enabled:
        logger.info(f"✅ SQS ready: {settings.PREDICTIONS_QUEUE_URL}")
    else:
        logger.warning("⚠️  SQS disabled: Set PREDICTIONS_QUEUE_URL to enable")


async def shutdown_sqs():
    """
    Application shutdown hook
    
    Add to FastAPI:
        @app.on_event("shutdown")
        async def shutdown():
            await shutdown_sqs()
    """
    logger.info("🛑 Shutting down SQS client...")
    sqs_client.close()

