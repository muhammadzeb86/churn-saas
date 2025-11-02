"""
SQS Message Publisher
=====================
Production-grade SQS message publishing with validation and error handling.

Features:
- Pydantic message validation
- Graceful degradation
- User-friendly error messages
- Retry tracking
- Structured logging
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.schemas.sqs_messages import PredictionSQSMessage
from backend.models import Prediction

logger = logging.getLogger(__name__)


async def publish_prediction_to_sqs(
    prediction_id: UUID,
    user_id: str,
    upload_id: UUID,
    s3_file_path: str,
    sqs_client: Optional[boto3.client],
    db: AsyncSession
) -> Tuple[bool, str]:
    """
    Publish prediction job to SQS with validation and error handling
    
    Args:
        prediction_id: UUID of prediction record
        user_id: Clerk user ID
        upload_id: UUID of upload record
        s3_file_path: S3 path to CSV file
        sqs_client: boto3 SQS client (injected)
        db: Database session
    
    Returns:
        (success: bool, user_message: str)
    
    Behavior:
        - If SQS disabled → mark for manual processing
        - If validation fails → return error
        - If publish succeeds → update prediction metadata
        - If publish fails → mark for retry with friendly message
    """
    
    # Check if SQS is enabled
    if not settings.is_sqs_enabled or not sqs_client:
        await _mark_for_manual_processing(db, prediction_id)
        return False, "Prediction saved - processing queue temporarily offline"
    
    try:
        # Validate message structure
        message = PredictionSQSMessage(
            prediction_id=prediction_id,
            user_id=user_id,
            upload_id=upload_id,
            s3_file_path=s3_file_path,
            timestamp=datetime.utcnow(),
            priority='normal'
        )
        
        # Publish to SQS
        response = sqs_client.send_message(
            QueueUrl=settings.PREDICTIONS_QUEUE_URL,
            MessageBody=message.json(),
            MessageAttributes={
                'user_id': {
                    'StringValue': user_id,
                    'DataType': 'String'
                },
                'prediction_id': {
                    'StringValue': str(prediction_id),
                    'DataType': 'String'
                },
                'upload_id': {
                    'StringValue': str(upload_id),
                    'DataType': 'String'
                }
            }
        )
        
        message_id = response['MessageId']
        
        # Update prediction record with SQS metadata
        await _update_prediction_metadata(
            db,
            prediction_id,
            message_id=message_id,
            queued_at=datetime.utcnow()
        )
        
        logger.info(
            f"✅ Published prediction to SQS",
            extra={
                'prediction_id': str(prediction_id),
                'user_id': user_id,
                'message_id': message_id,
                'queue': settings.sqs_queue_name
            }
        )
        
        return True, "Prediction queued for processing (estimated 2-5 minutes)"
        
    except ValidationError as e:
        # Message validation failed (should be caught earlier)
        logger.error(
            f"❌ Message validation failed",
            extra={
                'prediction_id': str(prediction_id),
                'user_id': user_id,
                'error': str(e)
            }
        )
        return False, "Invalid prediction data - please contact support"
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        # Map AWS errors to user-friendly messages
        user_messages = {
            'QueueDoesNotExist': "Processing service temporarily unavailable",
            'AccessDenied': "System configuration error - please contact support",
            'RequestThrottled': "High demand - your request has been saved",
            'InvalidMessageContents': "Invalid prediction data",
        }
        
        user_msg = user_messages.get(
            error_code,
            "Processing delayed - we'll retry automatically"
        )
        
        # Mark prediction for retry
        await _mark_for_retry(
            db,
            prediction_id,
            error_type='SQS_CLIENT_ERROR',
            error_code=error_code,
            error_message=error_message
        )
        
        logger.error(
            f"❌ SQS ClientError",
            extra={
                'prediction_id': str(prediction_id),
                'user_id': user_id,
                'error_code': error_code,
                'error_message': error_message
            }
        )
        
        return False, user_msg
        
    except BotoCoreError as e:
        # Low-level boto3 errors (network, etc.)
        logger.error(
            f"❌ SQS BotoCoreError",
            extra={
                'prediction_id': str(prediction_id),
                'user_id': user_id,
                'error': str(e)
            },
            exc_info=True
        )
        
        await _mark_for_retry(
            db,
            prediction_id,
            error_type='SQS_NETWORK_ERROR',
            error_message=str(e)
        )
        
        return False, "Network error - your prediction will be retried"
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"❌ Unexpected error publishing to SQS",
            extra={
                'prediction_id': str(prediction_id),
                'user_id': user_id,
                'error': str(e)
            },
            exc_info=True
        )
        
        await _mark_for_retry(
            db,
            prediction_id,
            error_type='UNKNOWN_ERROR',
            error_message=str(e)
        )
        
        return False, "System error - your prediction has been saved for processing"


# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def _update_prediction_metadata(
    db: AsyncSession,
    prediction_id: UUID,
    message_id: str,
    queued_at: datetime
):
    """Update prediction record with SQS metadata"""
    try:
        async with db.begin():
            prediction = await db.get(Prediction, prediction_id)
            if prediction:
                prediction.sqs_message_id = message_id
                prediction.sqs_queued_at = queued_at
                prediction.status = 'QUEUED'
    except Exception as e:
        logger.error(f"Failed to update prediction metadata: {str(e)}")


async def _mark_for_retry(
    db: AsyncSession,
    prediction_id: UUID,
    error_type: str,
    error_code: str = None,
    error_message: str = None
):
    """Mark prediction for automatic retry"""
    try:
        async with db.begin():
            prediction = await db.get(Prediction, prediction_id)
            if prediction:
                prediction.status = 'RETRY_PENDING'
                prediction.retry_count = (prediction.retry_count or 0) + 1
                prediction.last_error_type = error_type
                prediction.last_error_code = error_code
                prediction.last_error_message = error_message[:500] if error_message else None
                prediction.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
    except Exception as e:
        logger.error(f"Failed to mark prediction for retry: {str(e)}")


async def _mark_for_manual_processing(
    db: AsyncSession,
    prediction_id: UUID
):
    """Mark prediction for manual processing when SQS is disabled"""
    try:
        async with db.begin():
            prediction = await db.get(Prediction, prediction_id)
            if prediction:
                prediction.status = 'MANUAL_PROCESSING_REQUIRED'
                prediction.notes = 'SQS was disabled when this prediction was created'
    except Exception as e:
        logger.error(f"Failed to mark prediction for manual processing: {str(e)}")

