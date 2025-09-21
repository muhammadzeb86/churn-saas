import os
import boto3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Settings:
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    PREDICTIONS_QUEUE_URL: str = os.getenv("PREDICTIONS_QUEUE_URL", "")
    
    # S3 Configuration (existing)
    S3_BUCKET: str = os.getenv("S3_BUCKET", "retainwise-uploads")
    PREDICTIONS_BUCKET: str = os.getenv("PREDICTIONS_BUCKET", os.getenv("S3_BUCKET", "retainwise-uploads"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    def __init__(self):
        """Validate required settings on initialization"""
        # Configure SQL logging based on environment
        self.configure_sql_logging()
        
        # SQS is optional - will be enabled when queue is available
        if self.ENVIRONMENT == "production" and not self.PREDICTIONS_QUEUE_URL:
            import logging
            logging.getLogger(__name__).warning("PREDICTIONS_QUEUE_URL not set - SQS functionality disabled")
    
    def get_boto3_sqs(self):
        """Get configured boto3 SQS client"""
        try:
            return boto3.client("sqs", region_name=self.AWS_REGION)
        except Exception as e:
            logger.error(f"Failed to create SQS client: {e}")
            raise
    
    def get_boto3_s3(self):
        """Get configured boto3 S3 client"""
        try:
            return boto3.client("s3", region_name=self.AWS_REGION)
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            raise
    
    def mask_queue_url(self) -> str:
        """Mask SQS URL for logging (show only queue name)"""
        if not self.PREDICTIONS_QUEUE_URL:
            return "NOT_SET"
        
        try:
            # Extract queue name from URL
            # Format: https://sqs.region.amazonaws.com/account/queue-name
            queue_name = self.PREDICTIONS_QUEUE_URL.split("/")[-1]
            return f"***/{queue_name}"
        except:
            return "INVALID_URL"
    
    def configure_sql_logging(self):
        """Configure SQL logging based on environment"""
        if self.ENVIRONMENT == "production":
            # PRODUCTION: Disable SQL query logging for performance and security
            logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
            logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
            logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
            logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
            logger.info("SQL logging disabled for production environment")
        else:
            # DEVELOPMENT: Enable SQL query logging for debugging
            logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
            logger.info("SQL logging enabled for development environment")
    
    def log_config(self):
        """Log configuration at startup (with sensitive data masked)"""
        logger.info("=== Application Configuration ===")
        logger.info(f"Environment: {self.ENVIRONMENT}")
        logger.info(f"AWS Region: {self.AWS_REGION}")
        logger.info(f"S3 Bucket: {self.S3_BUCKET}")
        logger.info(f"Predictions Queue: {self.mask_queue_url()}")
        logger.info(f"Database URL: {'SET' if self.DATABASE_URL else 'NOT_SET'}")
        logger.info("================================")

# Global settings instance
settings = Settings()
