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
from backend.ml.feature_validator import SaaSFeatureValidator, ValidationLevel
from backend.ml.simple_explainer import get_simple_explainer
from backend.services.s3_service import s3_service
from backend.services.prediction_router import get_prediction_router
from backend.services.data_collector import get_data_collector
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
            # Initialize prediction router for A/B testing (Task 1.7)
            # Routes between Telecom model (control) and SaaS baseline (treatment)
            router = get_prediction_router()
            data_collector = get_data_collector()
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
        
        # ========================================
        # FEATURE VALIDATION (Task 1.6)
        # ========================================
        # Validate data quality AFTER column mapping, BEFORE ML prediction
        # This catches data quality issues early with actionable feedback
        
        validation_start = time.time()
        try:
            logger.info(
                "Starting feature validation",
                extra={
                    "event": "feature_validation_start",
                    "rows": len(mapped_df),
                    "columns": len(mapped_df.columns)
                }
            )
            
            # Validate with STANDARD level (best practices, not ML_TRAINING)
            validator = SaaSFeatureValidator(level=ValidationLevel.STANDARD)
            validation_result = validator.validate(mapped_df)
            
            validation_duration = time.time() - validation_start
            
            # Track validation metrics (for CloudWatch monitoring)
            await metrics.record_time(
                "FeatureValidationDuration",
                validation_duration,
                namespace=MetricNamespace.WORKER
            )
            
            await metrics.put_metric(
                "DataQualityScore",
                validation_result.metrics.get('quality_score', 0),
                MetricUnit.PERCENT,
                namespace=MetricNamespace.WORKER,
                dimensions={"TargetMarket": "saas"}
            )
            
            # If validation fails (blocking errors), reject prediction
            if not validation_result.is_valid:
                # Build detailed error message from first 3 errors
                error_summary = '\n'.join([
                    f"• {error.field}: {error.message} → {error.action}"
                    for error in validation_result.errors[:3]
                ])
                
                error_msg = (
                    f"Data validation failed ({len(validation_result.errors)} error(s)):\n"
                    f"{error_summary}\n\n"
                    f"Please fix these issues and try again."
                )
                
                logger.error(
                    f"Feature validation failed: {len(validation_result.errors)} error(s)",
                    extra={
                        "event": "feature_validation_failed",
                        "quality_score": validation_result.metrics.get('quality_score', 0),
                        "error_count": len(validation_result.errors),
                        "warning_count": len(validation_result.warnings),
                        "errors": [
                            {
                                'field': e.field,
                                'message': e.message,
                                'affected_rows': e.affected_rows
                            }
                            for e in validation_result.errors[:5]
                        ]
                    }
                )
                
                await metrics.increment_counter(
                    "FeatureValidationFailure",
                    namespace=MetricNamespace.WORKER,
                    dimensions={"ErrorType": "DataQualityError"}
                )
                
                raise ValueError(error_msg)
            
            # Log warnings (but proceed with prediction)
            if validation_result.warnings:
                warning_summary = ', '.join([w.field for w in validation_result.warnings[:3]])
                logger.warning(
                    f"Feature validation passed with {len(validation_result.warnings)} warning(s): {warning_summary}",
                    extra={
                        "event": "feature_validation_warnings",
                        "warning_count": len(validation_result.warnings),
                        "quality_score": validation_result.metrics.get('quality_score', 0)
                    }
                )
            
            # Success metrics
            await metrics.increment_counter(
                "FeatureValidationSuccess",
                namespace=MetricNamespace.WORKER,
                dimensions={"TargetMarket": "saas"}
            )
            
            logger.info(
                f"Feature validation passed: quality_score={validation_result.metrics.get('quality_score', 0):.1f}%, "
                f"warnings={len(validation_result.warnings)}, duration={validation_duration:.3f}s",
                extra={
                    "event": "feature_validation_success",
                    "quality_score": validation_result.metrics.get('quality_score', 0),
                    "completeness": validation_result.metrics.get('completeness_score', 0),
                    "errors": len(validation_result.errors),
                    "warnings": len(validation_result.warnings),
                    "duration_ms": validation_duration * 1000
                }
            )
            
        except ValueError as e:
            # Validation failed - already logged
            raise
        except Exception as e:
            # Unexpected validation error
            await metrics.increment_counter(
                "FeatureValidationFailure",
                namespace=MetricNamespace.WORKER,
                dimensions={"ErrorType": type(e).__name__}
            )
            logger.error(f"Unexpected validation error: {str(e)}")
            raise ValueError(f"Feature validation failed: {str(e)}")
        
        # Run predictions (ML inference) with mapped DataFrame via A/B router
        ml_prediction_start = time.time()
        
        # Route prediction to appropriate model (A/B test: Telecom vs SaaS baseline)
        prediction_result = router.route_prediction(mapped_df)
        
        # Handle batch vs single prediction
        if 'predictions' in prediction_result:
            # Batch prediction
            predictions_df = pd.DataFrame(prediction_result['predictions'])
        else:
            # Single prediction - convert to DataFrame
            predictions_df = pd.DataFrame([prediction_result])
        
        ml_prediction_duration = time.time() - ml_prediction_start
        
        # Log prediction for future model training (collect real data!)
        try:
            for idx, row in mapped_df.iterrows():
                customer_data = row.to_dict()
                pred_data = predictions_df.iloc[idx].to_dict() if idx < len(predictions_df) else prediction_result
                await data_collector.record_prediction(
                    customer_data=customer_data,
                    prediction_result=pred_data,
                    prediction_id=str(prediction_id)
                )
        except Exception as e:
            logger.warning(f"Failed to log prediction for training: {e}")
            # Don't fail prediction if logging fails
        
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
        
        # ========================================
        # SIMPLE EXPLANATIONS (Task 1.9 - MVP)
        # ========================================
        # Generate fast, actionable explanations using feature importance
        # SHAP deferred until 100+ customers and validated demand
        
        explanation_start = time.time()
        try:
            logger.info("Generating simple explanations for predictions...")
            
            # Get simple explainer (cached, fast)
            explainer = get_simple_explainer(
                model=router.telecom_predictor.model,  # Use the actual model
                feature_names=mapped_df.columns.tolist()
            )
            
            # Generate explanations for all predictions
            churn_probs = predictions_df['churn_probability'].tolist() if 'churn_probability' in predictions_df.columns else [0.5] * len(predictions_df)
            customer_ids = mapped_df['customerID'].tolist()
            
            explanations = explainer.explain_batch(
                customer_data=mapped_df,
                customer_ids=customer_ids,
                churn_probabilities=churn_probs,
                top_n=3  # Top 3 factors
            )
            
            # Convert to dict format for storage
            explanations_dict = [exp.to_dict() for exp in explanations]
            
            # Add explanations to predictions DataFrame
            # CRITICAL: Convert dicts to JSON strings for CSV compatibility
            predictions_df['explanation'] = [json.dumps(exp, ensure_ascii=False) for exp in explanations_dict]
            
            # Also format risk_factors and protective_factors for readability
            if 'risk_factors' in predictions_df.columns:
                predictions_df['risk_factors'] = predictions_df['risk_factors'].apply(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
                )
            
            if 'protective_factors' in predictions_df.columns:
                predictions_df['protective_factors'] = predictions_df['protective_factors'].apply(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
                )
            
            explanation_duration = time.time() - explanation_start
            avg_time = (explanation_duration / len(explanations) * 1000) if explanations else 0
            
            # Track metrics
            await metrics.record_time(
                "ExplanationGenerationDuration",
                explanation_duration,
                namespace=MetricNamespace.WORKER
            )
            
            await metrics.put_metric(
                "ExplanationAvgTimePerCustomer",
                avg_time,
                MetricUnit.MILLISECONDS,
                namespace=MetricNamespace.WORKER
            )
            
            await metrics.increment_counter(
                "ExplanationGenerationSuccess",
                namespace=MetricNamespace.WORKER,
                dimensions={"Method": "feature_importance"}
            )
            
            logger.info(
                f"Explanations generated: {len(explanations)} customers in {explanation_duration:.3f}s "
                f"(avg: {avg_time:.2f}ms per customer)",
                extra={
                    "event": "explanation_generation_success",
                    "customer_count": len(explanations),
                    "avg_time_ms": avg_time,
                    "method": "feature_importance"
                }
            )
            
        except Exception as e:
            # Explanation failed - log but don't fail prediction
            logger.error(f"Failed to generate explanations: {e}", exc_info=True)
            await metrics.increment_counter(
                "ExplanationGenerationFailure",
                namespace=MetricNamespace.WORKER,
                dimensions={"ErrorType": type(e).__name__}
            )
            # Add placeholder explanation column if missing
            if 'explanation' not in predictions_df.columns:
                predictions_df['explanation'] = None
        
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
 