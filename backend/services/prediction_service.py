"""
Prediction processing service
"""
import asyncio
import logging
import tempfile
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Union

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.api.database import get_async_session
from backend.models import Prediction, Upload, PredictionStatus
from backend.ml.predict import RetentionPredictor
from backend.services.s3_service import s3_service

logger = logging.getLogger(__name__)

async def process_prediction(prediction_id: Union[str, uuid.UUID], upload_id: str, user_id: str, s3_key: str) -> None:
    """
    Process a single prediction task
    
    Args:
        prediction_id: UUID of the prediction record
        upload_id: ID of the upload record
        user_id: ID of the user
        s3_key: S3 object key for the uploaded file
    """
    # Convert prediction_id to UUID if it's a string
    if isinstance(prediction_id, str):
        prediction_id = uuid.UUID(prediction_id)
    
    logger.info(
        "Starting prediction processing",
        extra={
            "event": "prediction_service_started",
            "prediction_id": str(prediction_id),
            "upload_id": upload_id,
            "user_id": user_id,
            "s3_key": s3_key
        }
    )
    
    temp_input_file = None
    temp_output_file = None
    
    try:
        async with get_async_session() as db:
            # Check if prediction already completed (idempotency)
            result = await db.execute(
                select(Prediction).where(Prediction.id == prediction_id)
            )
            prediction = result.scalar_one_or_none()
            
            if not prediction:
                raise ValueError(f"Prediction {prediction_id} not found")
            
            if prediction.status == PredictionStatus.COMPLETED:
                logger.info(
                    "Prediction already completed, skipping",
                    extra={
                        "event": "prediction_already_completed",
                        "prediction_id": str(prediction_id)
                    }
                )
                return
            
            # Get upload record
            upload_result = await db.execute(
                select(Upload).where(Upload.id == int(upload_id))
            )
            upload = upload_result.scalar_one_or_none()
            
            if not upload:
                raise ValueError(f"Upload {upload_id} not found")
        
        # Step 1: Download input CSV from S3
        logger.info(
            "Downloading input file from S3",
            extra={
                "event": "s3_download_started",
                "prediction_id": str(prediction_id),
                "s3_key": s3_key
            }
        )
        
        temp_input_file = tempfile.NamedTemporaryFile(
            mode='wb', 
            suffix='.csv', 
            delete=False
        )
        temp_input_file.close()
        
        # Download file from S3
        download_result = s3_service.download_file(s3_key, temp_input_file.name)
        if not download_result.get('success', False):
            raise Exception(f"Failed to download file from S3: {download_result.get('error')}")
        
        logger.info(
            "Successfully downloaded input file",
            extra={
                "event": "s3_download_completed",
                "prediction_id": str(prediction_id),
                "local_path": temp_input_file.name
            }
        )
        
        # Step 2: Run batch predictions using existing RetentionPredictor
        logger.info(
            "Starting ML prediction processing",
            extra={
                "event": "ml_processing_started",
                "prediction_id": prediction_id
            }
        )
        
        # Initialize the predictor
        predictor = RetentionPredictor()
        
        # Load input data
        input_df = pd.read_csv(temp_input_file.name)
        original_row_count = len(input_df)
        
        # Run predictions
        predictions_df = predictor.predict(input_df)
        
        # Calculate metrics
        if 'retention_prediction' in predictions_df.columns:
            positive_rate = predictions_df['retention_prediction'].mean()
        else:
            positive_rate = 0.0
        
        metrics = {
            "rows_processed": len(predictions_df),
            "original_rows": original_row_count,
            "positive_rate": float(positive_rate),
            "processing_timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "ML prediction processing completed",
            extra={
                "event": "ml_processing_completed",
                "prediction_id": str(prediction_id),
                "rows_processed": metrics["rows_processed"],
                "positive_rate": metrics["positive_rate"]
            }
        )
        
        # Step 3: Save predictions to temporary file
        temp_output_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False
        )
        temp_output_file.close()
        
        predictions_df.to_csv(temp_output_file.name, index=False)
        
        # Step 4: Upload output to S3
        output_s3_key = f"predictions/{user_id}/{prediction_id}.csv"
        
        logger.info(
            "Uploading prediction results to S3",
            extra={
                "event": "s3_upload_started",
                "prediction_id": str(prediction_id),
                "output_s3_key": output_s3_key
            }
        )
        
        # Read the output file and upload
        with open(temp_output_file.name, 'rb') as f:
            file_content = f.read()
        
        upload_result = s3_service.upload_file_stream(
            file_content=file_content,
            user_id=user_id,
            filename=f"{prediction_id}.csv"
        )
        
        if not upload_result.get('success', False):
            raise Exception(f"Failed to upload results to S3: {upload_result.get('error')}")
        
        actual_s3_key = upload_result.get('object_key', output_s3_key)
        
        logger.info(
            "Successfully uploaded prediction results",
            extra={
                "event": "s3_upload_completed",
                "prediction_id": str(prediction_id),
                "s3_key": actual_s3_key
            }
        )
        
        # Step 5: Update database records
        async with get_async_session() as db:
            # Update prediction record
            result = await db.execute(
                select(Prediction).where(Prediction.id == prediction_id)
            )
            prediction = result.scalar_one_or_none()
            
            if prediction:
                prediction.status = PredictionStatus.COMPLETED
                prediction.s3_output_key = actual_s3_key
                prediction.rows_processed = metrics["rows_processed"]
                prediction.metrics_json = metrics
                prediction.error_message = None
                prediction.updated_at = datetime.utcnow()
            
            # Update upload record
            upload_result = await db.execute(
                select(Upload).where(Upload.id == int(upload_id))
            )
            upload = upload_result.scalar_one_or_none()
            
            if upload:
                upload.status = "processed"
                upload.updated_at = datetime.utcnow()
            
            await db.commit()
        
        logger.info(
            "Prediction processing completed successfully",
            extra={
                "event": "prediction_service_completed",
                "prediction_id": str(prediction_id),
                "upload_id": upload_id,
                "user_id": user_id,
                "rows_processed": metrics["rows_processed"],
                "s3_output_key": actual_s3_key
            }
        )
        
    except Exception as e:
        logger.error(
            f"Prediction processing failed: {str(e)}",
            extra={
                "event": "prediction_service_failed",
                "prediction_id": str(prediction_id),
                "upload_id": upload_id,
                "user_id": user_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise
    
    finally:
        # Clean up temporary files
        if temp_input_file and os.path.exists(temp_input_file.name):
            try:
                os.unlink(temp_input_file.name)
                logger.debug(f"Cleaned up temp input file: {temp_input_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp input file: {e}")
        
        if temp_output_file and os.path.exists(temp_output_file.name):
            try:
                os.unlink(temp_output_file.name)
                logger.debug(f"Cleaned up temp output file: {temp_output_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp output file: {e}") 