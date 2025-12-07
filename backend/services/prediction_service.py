"""
Prediction processing service
"""
import asyncio
import logging
import tempfile
import os
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Union

import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.api.database import get_async_session
from backend.models import Prediction, Upload, PredictionStatus
from backend.ml.predict import RetentionPredictor
from backend.ml.column_mapper import IntelligentColumnMapper
from backend.services.s3_service import s3_service
from backend.monitoring.metrics import get_metrics_client, MetricUnit, MetricNamespace

logger = logging.getLogger(__name__)
metrics = get_metrics_client()

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
        s3_download_start = time.time()
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
            await metrics.increment_counter(
                "S3DownloadFailure",
                namespace=MetricNamespace.WORKER
            )
            raise Exception(f"Failed to download file from S3: {download_result.get('error')}")
        
        # Track S3 download duration
        s3_download_duration = time.time() - s3_download_start
        await metrics.record_time(
            "S3DownloadDuration",
            s3_download_duration,
            namespace=MetricNamespace.WORKER
        )
        
        logger.info(
            f"Successfully downloaded input file in {s3_download_duration:.2f}s",
            extra={
                "event": "s3_download_completed",
                "prediction_id": str(prediction_id),
                "local_path": temp_input_file.name,
                "duration": s3_download_duration
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
        
        # Initialize the predictor (model loading)
        model_load_start = time.time()
        try:
            predictor = RetentionPredictor()
            model_load_duration = time.time() - model_load_start
            
            await metrics.record_time(
                "ModelLoadDuration",
                model_load_duration,
                namespace=MetricNamespace.WORKER,
                dimensions={"ColdStart": "false"}  # Would be "true" on first load
            )
        except Exception as e:
            await metrics.increment_counter(
                "ModelLoadError",
                namespace=MetricNamespace.WORKER,
                dimensions={"ErrorType": type(e).__name__}
            )
            raise
        
        # Load input data (CSV parsing)
        csv_parse_start = time.time()
        input_df = pd.read_csv(temp_input_file.name)
        original_row_count = len(input_df)
        csv_parse_duration = time.time() - csv_parse_start
        
        await metrics.record_time(
            "CSVParseDuration",
            csv_parse_duration,
            namespace=MetricNamespace.WORKER
        )
        
        await metrics.put_metric(
            "CSVRowCount",
            original_row_count,
            MetricUnit.COUNT,
            namespace=MetricNamespace.WORKER,
            dimensions={"RowBucket": _get_row_bucket(original_row_count)}
        )
        
        # ========================================
        # COLUMN MAPPING INTEGRATION (Task 1.5)
        # ========================================
        # SAAS-ONLY FOCUS (100% Production-Grade)
        # RetainWise targets ONLY SaaS companies - no industry detection needed
        # The SaaS column mapper handles ALL SaaS variations:
        # - Stripe exports, Chargebee, ChartMogul, Custom systems
        # - 200+ column aliases for maximum compatibility
        # - Works with ANY real SaaS company CSV
        
        logger.info(
            "Column mapping: SaaS-only focus (RetainWise = SaaS churn prediction platform)",
            extra={
                "event": "column_mapping_start",
                "target_market": "saas_only",
                "s3_key": s3_key
            }
        )
        
        # Apply intelligent column mapping (SaaS-only)
        column_mapping_start = time.time()
        try:
            # SaaS-only mapper (handles ALL SaaS CSV variations)
            mapper = IntelligentColumnMapper(industry='saas')
            mapping_report = mapper.map_columns(input_df)
            
            # Check if mapping was successful
            if not mapping_report.success:
                missing_cols = ', '.join(mapping_report.missing_required)
                error_msg = (
                    f"Missing required columns: {missing_cols}. "
                    f"Please ensure your CSV has columns for: customerID, tenure, MonthlyCharges, TotalCharges, Contract."
                )
                
                # Add suggestions if available
                if mapping_report.suggestions:
                    error_msg += f" Suggestions: {'; '.join(mapping_report.suggestions[:3])}"
                
                logger.error(
                    f"Column mapping failed: {error_msg}",
                    extra={
                        "event": "column_mapping_failed",
                        "missing_columns": mapping_report.missing_required,
                        "mapped_columns": len(mapping_report.matches),
                        "confidence": mapping_report.confidence_avg
                    }
                )
                raise ValueError(error_msg)
            
            # Apply mapping to DataFrame (standardizes columns)
            mapped_df = mapper.apply_mapping(input_df, mapping_report)
            
            column_mapping_duration = time.time() - column_mapping_start
            
            # Log mapping success
            logger.info(
                f"Column mapping successful: {len(mapping_report.matches)} columns mapped, "
                f"confidence: {mapping_report.confidence_avg:.1f}%, "
                f"duration: {column_mapping_duration:.3f}s",
                extra={
                    "event": "column_mapping_success",
                    "target_market": "saas",
                    "columns_mapped": len(mapping_report.matches),
                    "confidence_avg": mapping_report.confidence_avg,
                    "duration_ms": column_mapping_duration * 1000
                }
            )
            
            # Track column mapping metrics
            await metrics.record_time(
                "ColumnMappingDuration",
                column_mapping_duration,
                namespace=MetricNamespace.WORKER
            )
            
            await metrics.put_metric(
                "ColumnMappingConfidence",
                mapping_report.confidence_avg,
                MetricUnit.PERCENT,
                namespace=MetricNamespace.WORKER,
                dimensions={"TargetMarket": "saas"}
            )
            
            await metrics.increment_counter(
                "ColumnMappingSuccess",
                namespace=MetricNamespace.WORKER,
                dimensions={"TargetMarket": "saas"}
            )
            
        except ValueError as e:
            # Column mapping validation failed
            await metrics.increment_counter(
                "ColumnMappingFailure",
                namespace=MetricNamespace.WORKER,
                dimensions={"ErrorType": "MissingColumns"}
            )
            logger.error(f"Column mapping validation failed: {str(e)}")
            raise
        except Exception as e:
            # Unexpected column mapping error
            await metrics.increment_counter(
                "ColumnMappingFailure",
                namespace=MetricNamespace.WORKER,
                dimensions={"ErrorType": type(e).__name__}
            )
            logger.error(f"Unexpected column mapping error: {str(e)}")
            raise ValueError(f"Column mapping failed: {str(e)}")
        
        # Run predictions (ML inference) with mapped DataFrame
        ml_prediction_start = time.time()
        predictions_df = predictor.predict(mapped_df)  # Use mapped_df instead of input_df
        ml_prediction_duration = time.time() - ml_prediction_start
        
        # Track ML prediction duration
        await metrics.record_time(
            "MLPredictionDuration",
            ml_prediction_duration,
            namespace=MetricNamespace.WORKER,
            dimensions={"RowBucket": _get_row_bucket(original_row_count)}
        )
        
        # Track throughput (rows/second)
        throughput = original_row_count / ml_prediction_duration if ml_prediction_duration > 0 else 0
        await metrics.put_metric(
            "PredictionThroughput",
            throughput,
            MetricUnit.NONE,
            namespace=MetricNamespace.WORKER,
            dimensions={"ModelVersion": "v1.0"}
        )
        
        # Calculate metrics
        if 'retention_prediction' in predictions_df.columns:
            positive_rate = predictions_df['retention_prediction'].mean()
        else:
            positive_rate = 0.0
        
        # ML-SPECIFIC METRIC: Prediction confidence (if available)
        if 'retention_probability' in predictions_df.columns:
            avg_confidence = predictions_df['retention_probability'].mean() * 100
            await metrics.put_metric(
                "PredictionConfidenceAvg",
                avg_confidence,
                MetricUnit.PERCENT,
                namespace=MetricNamespace.ML_PIPELINE,
                dimensions={"ModelVersion": "v1.0"}
            )
            
            # Track low-confidence predictions
            low_confidence_count = (predictions_df['retention_probability'] < 0.6).sum()
            low_confidence_pct = (low_confidence_count / len(predictions_df)) * 100
            await metrics.put_metric(
                "LowConfidencePredictionsPct",
                low_confidence_pct,
                MetricUnit.PERCENT,
                namespace=MetricNamespace.ML_PIPELINE
            )
        
        pred_metrics = {
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
                "rows_processed": pred_metrics["rows_processed"],
                "positive_rate": pred_metrics["positive_rate"]
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
        
        s3_upload_start = time.time()
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
            await metrics.increment_counter(
                "S3UploadFailure",
                namespace=MetricNamespace.WORKER,
                dimensions={"FileType": "results"}
            )
            raise Exception(f"Failed to upload results to S3: {upload_result.get('error')}")
        
        actual_s3_key = upload_result.get('object_key', output_s3_key)
        
        # Track S3 upload duration
        s3_upload_duration = time.time() - s3_upload_start
        await metrics.record_time(
            "S3UploadDuration",
            s3_upload_duration,
            namespace=MetricNamespace.WORKER,
            dimensions={"FileType": "results"}
        )
        
        logger.info(
            f"Successfully uploaded prediction results in {s3_upload_duration:.2f}s",
            extra={
                "event": "s3_upload_completed",
                "prediction_id": str(prediction_id),
                "s3_key": actual_s3_key,
                "duration": s3_upload_duration
            }
        )
        
        # Step 5: Update database records
        db_write_start = time.time()
        async with get_async_session() as db:
            # Update prediction record
            result = await db.execute(
                select(Prediction).where(Prediction.id == prediction_id)
            )
            prediction = result.scalar_one_or_none()
            
            if prediction:
                prediction.status = PredictionStatus.COMPLETED
                prediction.s3_output_key = actual_s3_key
                prediction.rows_processed = pred_metrics["rows_processed"]
                prediction.metrics_json = pred_metrics
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
        
        # Track database write duration
        db_write_duration = time.time() - db_write_start
        await metrics.record_time(
            "DatabaseWriteDuration",
            db_write_duration,
            namespace=MetricNamespace.DATABASE,
            dimensions={"Table": "predictions"}
        )
        
        await metrics.increment_counter(
            "PredictionsSaved",
            namespace=MetricNamespace.DATABASE,
            dimensions={"Table": "predictions", "RowCount": str(_get_row_bucket(original_row_count))}
        )
        
        logger.info(
            "Prediction processing completed successfully",
            extra={
                "event": "prediction_service_completed",
                "prediction_id": str(prediction_id),
                "upload_id": upload_id,
                "user_id": user_id,
                "rows_processed": pred_metrics["rows_processed"],
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


def _get_row_bucket(row_count: int) -> str:
    """
    Bucket row counts for dimension cardinality control.
    
    Prevents creating thousands of unique metric combinations.
    """
    if row_count < 100:
        return "<100"
    elif row_count < 1000:
        return "100-1000"
    elif row_count < 10000:
        return "1K-10K"
    elif row_count < 100000:
        return "10K-100K"
    else:
        return ">100K"
 