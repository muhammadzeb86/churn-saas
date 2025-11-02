"""
SQS Worker for Processing Prediction Tasks
===========================================
Production-grade worker with:
- Proper SQS message validation (Pydantic)
- Graceful shutdown handling
- Idempotency protection
- Comprehensive error handling
- Structured logging
- Visibility timeout management

Task 1.2: Deploy Worker Service
"""
import asyncio
import json
import logging
import signal
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.api.database import get_async_session
from backend.models import Prediction, PredictionStatus
from backend.services.prediction_service import process_prediction
from backend.schemas.sqs_messages import PredictionSQSMessage

logger = logging.getLogger(__name__)

class PredictionWorker:
    """
    Production-grade SQS worker for ML predictions
    
    Features:
    - Pydantic message validation
    - Graceful shutdown (SIGTERM/SIGINT)
    - Idempotency protection
    - Visibility timeout management
    - Structured logging
    """
    
    def __init__(self):
        self.sqs_client = settings.get_boto3_sqs()
        self.queue_url = settings.PREDICTIONS_QUEUE_URL
        self.running = False
        self.current_prediction_id = None
        self.current_receipt_handle = None
        self.messages_processed = 0
        self.messages_failed = 0
        
        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    async def start(self):
        """Start the worker loop with comprehensive logging"""
        logger.info("=" * 60)
        logger.info("🚀 Starting RetainWise Prediction Worker")
        logger.info("=" * 60)
        logger.info(f"Queue URL: {settings.mask_queue_url()}")
        logger.info(f"AWS Region: {settings.AWS_REGION}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"SQS Enabled: {settings.is_sqs_enabled}")
        logger.info("=" * 60)
        
        if not self.queue_url:
            logger.error("❌ PREDICTIONS_QUEUE_URL not configured")
            logger.error("Worker cannot start without queue URL")
            return
        
        if not settings.is_sqs_enabled:
            logger.error("❌ SQS is disabled (ENABLE_SQS=false)")
            logger.error("Worker cannot start when SQS is disabled")
            return
        
        self.running = True
        start_time = datetime.utcnow()
        
        logger.info("✅ Worker ready - polling for messages...")
        
        while self.running:
            try:
                await self._poll_and_process()
            except Exception as e:
                logger.error(
                    f"❌ Error in worker loop: {str(e)}",
                    extra={
                        "event": "worker_loop_error",
                        "error": str(e)
                    },
                    exc_info=True
                )
                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(5)
        
        # Shutdown summary
        uptime = (datetime.utcnow() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info("🛑 Prediction Worker Shutdown")
        logger.info(f"Uptime: {uptime:.2f} seconds")
        logger.info(f"Messages Processed: {self.messages_processed}")
        logger.info(f"Messages Failed: {self.messages_failed}")
        logger.info(f"Success Rate: {self._calculate_success_rate():.1f}%")
        logger.info("=" * 60)
    
    async def _poll_and_process(self):
        """Poll SQS for messages and process them"""
        try:
            # Long poll for messages
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            for message in messages:
                if not self.running:
                    break
                
                # Store receipt handle for visibility timeout extension
                self.current_receipt_handle = message['ReceiptHandle']
                
                try:
                    await self._process_message(message)
                    
                    # Delete message only on success
                    self.sqs_client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                    self.messages_processed += 1
                    
                    logger.info(
                        "✅ Message processed successfully",
                        extra={
                            "event": "message_processed",
                            "message_id": message.get('MessageId'),
                            "total_processed": self.messages_processed
                        }
                    )
                    
                except Exception as e:
                    self.messages_failed += 1
                    
                    logger.error(
                        f"❌ Failed to process message: {str(e)}",
                        extra={
                            "event": "message_processing_failed",
                            "message_id": message.get('MessageId'),
                            "error": str(e),
                            "total_failed": self.messages_failed
                        },
                        exc_info=True
                    )
                    # Don't delete message - let SQS handle retry/DLQ
                
                finally:
                    self.current_receipt_handle = None
                    
        except Exception as e:
            # Log but don't crash - this handles SQS connectivity issues
            logger.error(f"Error polling SQS: {str(e)}")
            await asyncio.sleep(1)
    
    async def _process_message(self, message: Dict[str, Any]):
        """
        Process a single SQS message with Pydantic validation
        
        Message format (from sqs_publisher.py):
        {
            "prediction_id": "uuid",
            "user_id": "user_xxx",
            "upload_id": "uuid",
            "s3_file_path": "s3://bucket/key",  # Note: NOT s3_key!
            "timestamp": "ISO8601",
            "priority": "normal"
        }
        """
        try:
            # Parse and validate message body with Pydantic
            body = json.loads(message['Body'])
            
            # Validate message structure
            try:
                validated_msg = PredictionSQSMessage(**body)
            except ValidationError as e:
                logger.error(
                    f"❌ Invalid SQS message structure",
                    extra={
                        "event": "message_validation_failed",
                        "message_id": message.get('MessageId'),
                        "errors": str(e),
                        "body": body
                    }
                )
                raise ValueError(f"Invalid message structure: {str(e)}")
            
            # Extract validated fields
            prediction_id = validated_msg.prediction_id
            upload_id = str(validated_msg.upload_id)
            user_id = validated_msg.user_id
            
            # Extract S3 key from s3_file_path
            # Format: s3://bucket-name/path/to/file.csv → path/to/file.csv
            s3_file_path = validated_msg.s3_file_path
            if s3_file_path.startswith('s3://'):
                # Remove s3:// prefix and bucket name
                s3_key = '/'.join(s3_file_path.split('/')[3:])
            else:
                # Already in key format
                s3_key = s3_file_path
            
            logger.info(
                "✅ Processing prediction task",
                extra={
                    "event": "prediction_processing_started",
                    "prediction_id": str(prediction_id),
                    "upload_id": upload_id,
                    "user_id": user_id,
                    "s3_key": s3_key,
                    "message_id": message.get('MessageId'),
                    "priority": validated_msg.priority
                }
            )
            
            self.current_prediction_id = prediction_id
            
            # Check prediction status and handle idempotency
            async with get_async_session() as db:
                # Get prediction record
                result = await db.execute(
                    select(Prediction).where(Prediction.id == prediction_id)
                )
                prediction = result.scalar_one_or_none()
                
                if not prediction:
                    logger.warning(
                        f"Prediction {prediction_id} not found in database",
                        extra={
                            "event": "prediction_not_found",
                            "prediction_id": str(prediction_id)
                        }
                    )
                    return  # Message will be deleted
                
                # Check if already completed or failed
                if prediction.status in [PredictionStatus.COMPLETED, PredictionStatus.FAILED]:
                    logger.info(
                        f"Prediction {prediction_id} already in final state: {prediction.status}",
                        extra={
                            "event": "prediction_already_processed",
                            "prediction_id": str(prediction_id),
                            "status": prediction.status.value
                        }
                    )
                    return  # Message will be deleted
                
                # Update status to RUNNING
                prediction.status = PredictionStatus.RUNNING
                prediction.updated_at = datetime.utcnow()
                await db.commit()
                
                logger.info(
                    "Prediction status updated to RUNNING",
                    extra={
                        "event": "prediction_status_updated",
                        "prediction_id": str(prediction_id),
                        "status": "RUNNING"
                    }
                )
            
            # Process the prediction
            await process_prediction(prediction_id, upload_id, user_id, s3_key)
            
            logger.info(
                "Prediction processing completed",
                extra={
                    "event": "prediction_processing_completed",
                    "prediction_id": str(prediction_id),
                    "upload_id": upload_id,
                    "user_id": user_id
                }
            )
            
        except Exception as e:
            # Update prediction status to FAILED
            if hasattr(self, 'current_prediction_id') and self.current_prediction_id:
                try:
                    async with get_async_session() as db:
                        result = await db.execute(
                            select(Prediction).where(Prediction.id == self.current_prediction_id)
                        )
                        prediction = result.scalar_one_or_none()
                        
                        if prediction:
                            prediction.status = PredictionStatus.FAILED
                            prediction.error_message = str(e)
                            prediction.updated_at = datetime.utcnow()
                            await db.commit()
                            
                            logger.error(
                                "Prediction status updated to FAILED",
                                extra={
                                    "event": "prediction_processing_failed",
                                    "prediction_id": str(self.current_prediction_id),
                                    "error": str(e)
                                }
                            )
                            
                except Exception as db_error:
                    logger.error(f"Failed to update prediction status to FAILED: {str(db_error)}")
            
            raise  # Re-raise to prevent message deletion
    
    def _calculate_success_rate(self) -> float:
        """Calculate message processing success rate"""
        total = self.messages_processed + self.messages_failed
        if total == 0:
            return 0.0
        return (self.messages_processed / total) * 100 