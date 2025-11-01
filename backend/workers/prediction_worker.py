"""
SQS Worker for processing prediction tasks
"""
import asyncio
import json
import logging
import signal
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.api.database import get_async_session
from backend.models import Prediction, PredictionStatus
from backend.services.prediction_service import process_prediction

logger = logging.getLogger(__name__)

class PredictionWorker:
    def __init__(self):
        self.sqs_client = settings.get_boto3_sqs()
        self.queue_url = settings.PREDICTIONS_QUEUE_URL
        self.running = False
        self.current_prediction_id = None
        
        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    async def start(self):
        """Start the worker loop"""
        logger.info("Starting prediction worker...")
        logger.info(f"Queue URL: {settings.mask_queue_url()}")
        
        if not self.queue_url:
            logger.error("PREDICTIONS_QUEUE_URL not configured")
            return
        
        self.running = True
        
        while self.running:
            try:
                await self._poll_and_process()
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(5)
        
        logger.info("Prediction worker stopped")
    
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
                
                try:
                    await self._process_message(message)
                    
                    # Delete message only on success
                    self.sqs_client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                    logger.info(
                        "Message processed successfully",
                        extra={
                            "event": "message_processed",
                            "message_id": message.get('MessageId')
                        }
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to process message: {str(e)}",
                        extra={
                            "event": "message_processing_failed",
                            "message_id": message.get('MessageId'),
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    # Don't delete message - let SQS handle retry/DLQ
                    
        except Exception as e:
            # Log but don't crash - this handles SQS connectivity issues
            logger.error(f"Error polling SQS: {str(e)}")
            await asyncio.sleep(1)
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process a single SQS message"""
        try:
            # Parse message body
            body = json.loads(message['Body'])
            
            prediction_id_str = body.get('prediction_id')
            upload_id = body.get('upload_id')
            user_id = body.get('user_id')
            s3_key = body.get('s3_key')
            
            # Validate required fields
            if not all([prediction_id_str, upload_id, user_id, s3_key]):
                raise ValueError(f"Missing required fields in message: {body}")
            
            # Convert prediction_id from string to UUID
            try:
                prediction_id = uuid.UUID(prediction_id_str)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid prediction_id format: {prediction_id_str}") from e
            
            logger.info(
                "Processing prediction task",
                extra={
                    "event": "prediction_processing_started",
                    "prediction_id": str(prediction_id),
                    "upload_id": upload_id,
                    "user_id": user_id
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