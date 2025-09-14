import os
import boto3
from typing import Optional
import logging

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
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    def __init__(self):
        """Validate required settings on initialization"""
        if self.ENVIRONMENT == "production" and not self.PREDICTIONS_QUEUE_URL:
            raise ValueError("PREDICTIONS_QUEUE_URL is required in production environment")
    
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
            queue_name = self.PREDICTIONS_QUEUE_URL.split('/')[-1]
            return f"***/{queue_name}"
        except:
            return "INVALID_URL"
    
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