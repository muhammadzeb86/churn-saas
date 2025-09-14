"""
SQS Service for publishing prediction tasks
"""
import json
import logging
import datetime
from typing import Dict, Any
from backend.core.config import settings

logger = logging.getLogger(__name__)

async def publish_prediction_task(
    queue_url: str,
    prediction_id: str,
    upload_id: str,
    user_id: str,
    s3_key: str
) -> Dict[str, Any]:
    """
    Publish a prediction task to SQS queue
    
    Args:
        queue_url: SQS queue URL
        prediction_id: UUID of the prediction record
        upload_id: ID of the upload record
        user_id: ID of the user
        s3_key: S3 object key for the uploaded file
        
    Returns:
        Dict containing message_id and success status
        
    Raises:
        Exception: If SQS publish fails
    """
    try:
        sqs_client = settings.get_boto3_sqs()
        
        # Create message body
        message_body = {
            "prediction_id": prediction_id,
            "upload_id": upload_id,
            "user_id": user_id,
            "s3_key": s3_key,
            "task_type": "ml_prediction",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Send message to SQS
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                'task_type': {
                    'StringValue': 'ml_prediction',
                    'DataType': 'String'
                },
                'user_id': {
                    'StringValue': user_id,
                    'DataType': 'String'
                }
            }
        )
        
        message_id = response['MessageId']
        logger.info(f"Published prediction task to SQS: message_id={message_id}, prediction_id={prediction_id}")
        
        return {
            "success": True,
            "message_id": message_id,
            "queue_url": queue_url
        }
        
    except Exception as e:
        logger.error(f"Failed to publish prediction task to SQS: {str(e)}")
        raise 