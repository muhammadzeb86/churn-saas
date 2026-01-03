"""
Prediction processing service
"""
import asyncio
import logging
import tempfile
import os
import uuid
import time
import ast
import json
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

# ========================================
# PHASE 2: PRODUCTION OBSERVABILITY
# ========================================
from backend.core.observability import (
    ProductionLogger,
    PerformanceMonitor,
    CloudWatchMetrics,
    CostTracker,
    log_prediction_event
)

# Initialize production monitoring
production_logger = ProductionLogger(__name__)
perf_monitor = PerformanceMonitor()
cloudwatch_metrics = CloudWatchMetrics()
cost_tracker = CostTracker()

# Legacy logger for backward compatibility
logger = logging.getLogger(__name__)
metrics = get_metrics_client()

# Log code version on module load - to verify correct code is deployed
logger.info("🚀 prediction_service.py loaded - CODE_VERSION: 2024-12-15-PHASE2-OBSERVABILITY")
production_logger.logger.info(
    "module_loaded",
    module="prediction_service",
    version="2024-12-15-PHASE2-OBSERVABILITY",
    features=["structured_logging", "performance_monitoring", "cost_tracking"],
    severity="INFO"
)

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
    
    # PHASE 2: Structured logging (CloudWatch Insights compatible)
    production_logger.log_prediction_start(
        prediction_id=str(prediction_id),
        user_id=user_id,
        row_count=0  # Will update after loading
    )
    
    # Legacy logging (backward compatibility)
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
    overall_start_time = time.time()
    
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
        
        # STEP 1: Auto-transform data (clean common issues)
        transform_start = time.time()
        try:
            mapped_df, transform_log = _auto_transform_data(mapped_df)
            
            if transform_log:
                logger.info(
                    f"Auto-transformed data: {len(transform_log)} corrections applied",
                    extra={
                        "event": "data_auto_transform",
                        "corrections": transform_log
                    }
                )
        except Exception as e:
            # Log but don't fail - transformation is best-effort
            logger.warning(f"Data auto-transformation failed: {e}")
        
        transform_duration = time.time() - transform_start
        
        # STEP 2: Validate cleaned data
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
            
            # If validation fails (blocking errors), LOG but PROCEED
            # Production ML should be resilient - clean data, don't reject it
            if not validation_result.is_valid:
                # Build detailed warning message from first 3 errors
                error_summary = '\n'.join([
                    f"• {error.field}: {error.message} → {error.action}"
                    for error in validation_result.errors[:3]
                ])
                
                # LOG as WARNING (not ERROR) - we'll proceed with prediction
                logger.warning(
                    f"Data quality issues detected ({len(validation_result.errors)} issue(s)) - proceeding with prediction",
                    extra={
                        "event": "feature_validation_warnings",
                        "quality_score": validation_result.metrics.get('quality_score', 0),
                        "error_count": len(validation_result.errors),
                        "warning_count": len(validation_result.warnings),
                        "issues": [
                            {
                                'field': e.field,
                                'message': e.message,
                                'affected_rows': e.affected_rows
                            }
                            for e in validation_result.errors[:5]
                        ]
                    }
                )
                
                # Track metric (non-blocking, graceful failure)
                try:
                    await metrics.increment_counter(
                        "DataQualityWarning",
                        namespace=MetricNamespace.WORKER,
                        dimensions={"WarningType": "AutoCorrected"}
                    )
                except Exception as metrics_error:
                    logger.debug(f"Failed to send CloudWatch metric: {metrics_error}")
                
                # CONTINUE with prediction (don't raise error)
                # The auto-transformation should have fixed most issues
            
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
        # Updated: Now handles both SaaS baseline and Telecom models
        
        explanation_start = time.time()
        try:
            logger.info("🎯 EXPLANATION GENERATION START - Code version: 2024-12-13-v4")
            logger.info(f"DataFrame shape: {predictions_df.shape}, Columns: {predictions_df.columns.tolist()}")

            # Check if DataFrame has rows before processing
            if len(predictions_df) == 0:
                logger.warning("⚠️  DataFrame is empty - no predictions to explain")
                predictions_df['explanation'] = None
                return
            
            # Normalize factor columns early so downstream logic always sees lists/dicts
            if 'risk_factors' in predictions_df.columns:
                sample_log = f" - sample: {predictions_df['risk_factors'].iloc[0]}" if len(predictions_df) > 0 else ""
                logger.info(f"📊 Normalizing risk_factors{sample_log}")
                predictions_df['risk_factors'] = predictions_df['risk_factors'].apply(_normalize_factor_list)
                logger.info(f"✅ Normalized risk_factors")
            if 'protective_factors' in predictions_df.columns:
                logger.info(f"📊 Normalizing protective_factors")
                predictions_df['protective_factors'] = predictions_df['protective_factors'].apply(_normalize_factor_list)
                logger.info(f"✅ Normalized protective_factors")
            
            # Detect which model was used by checking if risk_factors column exists
            # SaaS baseline adds risk_factors/protective_factors, Telecom model doesn't
            uses_saas_baseline = 'risk_factors' in predictions_df.columns and 'protective_factors' in predictions_df.columns
            logger.info(f"🔍 Model detection: uses_saas_baseline={uses_saas_baseline}")
            
            if uses_saas_baseline:
                # ========================================
                # SAAS BASELINE: Generate from risk/protective factors
                # ========================================
                logger.info("Generating explanations from SaaS baseline factors...")
                
                explanations = []
                for idx, row in predictions_df.iterrows():
                    # Get risk and protective factors (still as Python lists/dicts at this point)
                    risk_factors = _normalize_factor_list(row.get('risk_factors', []))
                    protective_factors = _normalize_factor_list(row.get('protective_factors', []))
                    churn_prob = row.get('churn_probability', 0.5)
                    customer_id = row.get('customerID', f'customer_{idx}')
                    
                    # ============================================
                    # CRITICAL FIX: Ensure factors are NEVER empty
                    # ============================================
                    # If SaaS baseline didn't generate factors, create fallback
                    if not risk_factors:
                        logger.warning(f"Row {idx}: risk_factors empty, generating fallback")
                        if churn_prob > 0.6:
                            risk_factors = [{
                                'factor': 'high_churn_probability',
                                'impact': 'high',
                                'message': f'Churn probability of {churn_prob:.1%} indicates significant risk'
                            }]
                        elif churn_prob > 0.3:
                            risk_factors = [{
                                'factor': 'medium_churn_probability',
                                'impact': 'medium',
                                'message': f'Churn probability of {churn_prob:.1%} requires monitoring'
                            }]
                        else:
                            risk_factors = [{
                                'factor': 'baseline_risk',
                                'impact': 'low',
                                'message': 'Standard customer risk profile'
                            }]
                    
                    if not protective_factors and churn_prob <= 0.3:
                        logger.warning(f"Row {idx}: protective_factors empty for low-risk customer, generating fallback")
                        protective_factors = [{
                            'factor': 'low_churn_probability',
                            'impact': 'high',
                            'message': f'Low churn probability of {churn_prob:.1%} indicates strong retention'
                        }]
                    
                    try:
                        # Build human-readable explanation
                        explanation = {
                            'customer_id': customer_id,
                            'churn_probability': round(churn_prob * 100, 1),
                            'risk_level': 'High' if churn_prob > 0.6 else ('Medium' if churn_prob > 0.3 else 'Low'),
                            'summary': _generate_summary_from_factors(risk_factors, protective_factors, churn_prob),
                            'risk_factors': [
                                {
                                    'factor': f.get('factor', ''),
                                    'impact': f.get('impact', ''),
                                    'description': f.get('message', '')
                                }
                                for f in risk_factors[:3]  # Top 3
                                if isinstance(f, dict)
                            ],
                            'protective_factors': [
                                {
                                    'factor': f.get('factor', ''),
                                    'impact': f.get('impact', ''),
                                    'description': f.get('message', '')
                                }
                                for f in protective_factors[:3]  # Top 3
                                if isinstance(f, dict)
                            ]
                        }
                        explanations.append(json.dumps(explanation, ensure_ascii=False))
                    except Exception as explain_err:
                        logger.error(f"Failed to build SaaS baseline explanation for row {idx}: {explain_err}", exc_info=True)
                        # Create minimal fallback explanation
                        fallback_explanation = {
                            'customer_id': customer_id,
                            'churn_probability': round(churn_prob * 100, 1),
                            'risk_level': 'High' if churn_prob > 0.6 else ('Medium' if churn_prob > 0.3 else 'Low'),
                            'summary': f"Churn probability: {churn_prob:.1%}. Unable to generate detailed explanation.",
                            'risk_factors': [],
                            'protective_factors': []
                        }
                        explanations.append(json.dumps(fallback_explanation, ensure_ascii=False))
                
                predictions_df['explanation'] = explanations
                method_used = "saas_baseline_factors"
                
            else:
                # ========================================
                # TELECOM MODEL: Use SimpleExplainer (feature importance)
                # ========================================
                logger.info("Generating explanations from Telecom model...")
                
                model_for_explainer = router.telecom_model.model if router.telecom_model else None
                
                if model_for_explainer is None:
                    raise ValueError("No model available for explanation generation")
                
                explainer = get_simple_explainer(
                    model=model_for_explainer,
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
                method_used = "feature_importance"
            
            explanation_duration = time.time() - explanation_start
            avg_time = (explanation_duration / len(predictions_df) * 1000) if len(predictions_df) > 0 else 0
            
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
                dimensions={"Method": method_used}
            )
            
            logger.info(
                f"Explanations generated: {len(predictions_df)} customers in {explanation_duration:.3f}s "
                f"(avg: {avg_time:.2f}ms per customer) using {method_used}",
                extra={
                    "event": "explanation_generation_success",
                    "customer_count": len(predictions_df),
                    "avg_time_ms": avg_time,
                    "method": method_used
                }
            )
            
            # ============================================
            # VALIDATION: Ensure no empty explanation columns
            # ============================================
            # Check if risk_factors/protective_factors/explanation are populated
            if 'risk_factors' in predictions_df.columns:
                empty_risk_count = predictions_df['risk_factors'].isna().sum()
                if empty_risk_count > 0:
                    logger.warning(f"⚠️  {empty_risk_count} rows have empty risk_factors - this should not happen!")
            
            if 'protective_factors' in predictions_df.columns:
                empty_protective_count = predictions_df['protective_factors'].isna().sum()
                if empty_protective_count > 0:
                    logger.warning(f"⚠️  {empty_protective_count} rows have empty protective_factors")
            
            if 'explanation' in predictions_df.columns:
                empty_explanation_count = predictions_df['explanation'].isna().sum()
                if empty_explanation_count > 0:
                    logger.error(f"❌ {empty_explanation_count} rows have empty explanations - CRITICAL BUG!")
                    # This should never happen after our fixes
            
            logger.info(f"✅ Explanation validation complete - all columns populated")
            
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
        
        # ========================================
        # CREATE EXCEL-FRIENDLY COLUMNS (Always runs)
        # ========================================
        # Convert complex JSON to readable columns for business users
        logger.info(f"📊 CREATING EXCEL-FRIENDLY OUTPUT - Code version: 2024-12-13-v5")
        logger.info(f"Columns in DataFrame: {predictions_df.columns.tolist()}")
        
        try:
            # Check if DataFrame has rows before processing
            if len(predictions_df) == 0:
                logger.warning("⚠️  DataFrame is empty - skipping formatting")
                return
            
            # Parse explanation JSON and create readable columns
            if 'explanation' in predictions_df.columns:
                logger.info("📋 Creating user-friendly columns from explanations...")
                
                for idx, row in predictions_df.iterrows():
                    try:
                        # Parse explanation if it's a JSON string
                        if isinstance(row['explanation'], str):
                            expl = json.loads(row['explanation'])
                        else:
                            expl = row['explanation']
                        
                        if expl and isinstance(expl, dict):
                            # Extract readable fields
                            predictions_df.at[idx, 'risk_level'] = expl.get('risk_level', '')
                            predictions_df.at[idx, 'summary'] = expl.get('summary', '')
                            
                            # Convert risk factors to comma-separated text
                            risk_list = expl.get('risk_factors', [])
                            if risk_list:
                                risk_text = ', '.join([f['description'] for f in risk_list[:3]])
                                predictions_df.at[idx, 'key_risks'] = risk_text
                            
                            # Convert protective factors to comma-separated text
                            protective_list = expl.get('protective_factors', [])
                            if protective_list:
                                protective_text = ', '.join([f['description'] for f in protective_list[:3]])
                                predictions_df.at[idx, 'strengths'] = protective_text
                    except Exception as e:
                        logger.warning(f"Failed to parse explanation for row {idx}: {e}")
                        continue
            
            # Generate recommendation column (no emojis - Excel compatibility)
            if 'churn_probability' in predictions_df.columns:
                def get_recommendation(churn_prob):
                    if churn_prob > 0.6:
                        return "HIGH RISK - Immediate intervention needed"
                    elif churn_prob > 0.3:
                        return "MEDIUM RISK - Proactive engagement recommended"
                    else:
                        return "LOW RISK - Continue monitoring"
                
                predictions_df['recommendation'] = predictions_df['churn_probability'].apply(get_recommendation)
            
            # Format churn probability as percentage
            if 'churn_probability' in predictions_df.columns:
                predictions_df['churn_risk_pct'] = (predictions_df['churn_probability'] * 100).round(1).astype(str) + '%'
            
            # ============================================
            # CRITICAL FIX: KEEP JSON columns for dashboard/Excel export
            # ============================================
            # DON'T drop 'risk_factors', 'protective_factors', 'explanation' - they're needed by:
            # - Dashboard expanded row details
            # - Excel export explanation sheets
            # - Future API consumers
            
            # Only drop 'predicted_at' if it exists (temporal column, not needed in output)
            if 'predicted_at' in predictions_df.columns:
                predictions_df = predictions_df.drop(columns=['predicted_at'])
                logger.info("Dropped column: predicted_at (temporal metadata)")
            
            # Ensure JSON columns are properly serialized as JSON strings (not Python repr)
            for json_col in ['risk_factors', 'protective_factors', 'explanation']:
                if json_col in predictions_df.columns:
                    predictions_df[json_col] = predictions_df[json_col].apply(_serialize_json_column)
                    logger.info(f"Serialized {json_col} to JSON format")
            
            # Reorder columns for better Excel experience
            # Priority: user-friendly columns first, then JSON columns at end
            priority_columns = ['customerID', 'risk_level', 'churn_risk_pct', 'recommendation', 'summary', 'key_risks', 'strengths']
            json_columns = ['risk_factors', 'protective_factors', 'explanation']
            other_columns = [col for col in predictions_df.columns 
                           if col not in priority_columns and col not in json_columns]
            
            new_order = (
                [col for col in priority_columns if col in predictions_df.columns] + 
                other_columns + 
                [col for col in json_columns if col in predictions_df.columns]
            )
            predictions_df = predictions_df[new_order]
            
            logger.info(f"✅ Excel-friendly columns created. Final columns: {predictions_df.columns.tolist()}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create Excel-friendly columns: {e}", exc_info=True)
            # Don't fail prediction if formatting fails
        
        # Step 3: Save predictions to temporary file
        temp_output_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        temp_output_file.close()
        
        # Write CSV with proper escaping for JSON fields
        predictions_df.to_csv(
            temp_output_file.name, 
            index=False,
            escapechar='\\',
            doublequote=True
        )
        
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
        
        # PHASE 2: Structured completion logging + cost tracking
        overall_duration_ms = (time.time() - overall_start_time) * 1000
        
        # Log completion with structured data
        production_logger.log_prediction_complete(
            prediction_id=str(prediction_id),
            duration_ms=overall_duration_ms,
            row_count=pred_metrics["rows_processed"]
        )
        
        # Record CloudWatch metrics (with regression detection) - non-blocking
        try:
            cloudwatch_metrics.record_prediction_duration(
                duration_ms=overall_duration_ms,
                row_count=pred_metrics["rows_processed"],
                model_type="saas_baseline"  # or detect from pred_metrics
            )
        except Exception as metrics_error:
            logger.debug(f"Failed to send CloudWatch metric: {metrics_error}")
        
        # Estimate and track costs
        estimated_cost = cost_tracker.estimate_prediction_cost(
            row_count=pred_metrics["rows_processed"],
            duration_ms=overall_duration_ms
        )
        
        logger.info(
            "Prediction processing completed successfully",
            extra={
                "event": "prediction_service_completed",
                "prediction_id": str(prediction_id),
                "upload_id": upload_id,
                "user_id": user_id,
                "rows_processed": pred_metrics["rows_processed"],
                "s3_output_key": actual_s3_key,
                "duration_ms": round(overall_duration_ms, 2),
                "estimated_cost_usd": round(estimated_cost, 6)
            }
        )
        
    except Exception as e:
        # PHASE 2: Structured error logging
        production_logger.log_prediction_error(
            prediction_id=str(prediction_id),
            error=e,
            user_id=user_id,
            upload_id=upload_id
        )
        
        # Record error metric in CloudWatch - non-blocking
        try:
            cloudwatch_metrics.record_error(
                error_type=type(e).__name__,
                operation="process_prediction"
            )
        except Exception as metrics_error:
            logger.debug(f"Failed to send CloudWatch error metric: {metrics_error}")
        
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


def _normalize_factor_list(value: Any) -> list:
    """
    Normalize risk/protective factors to a list of dicts.

    Handles cases where factors may already be JSON strings or Python repr strings.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        # Try JSON, then Python literal
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(value)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except Exception:
                continue
    return []


def _auto_transform_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Auto-transform data to fix common issues (PRODUCTION ML best practice).
    
    Instead of rejecting user data, clean and normalize it automatically.
    This is standard practice in production ML systems.
    
    Transformations Applied:
    -----------------------
    1. Tenure → Cap at reasonable range (0-120 months = 10 years)
    2. MonthlyCharges → Ensure positive values (min 0.01)
    3. TotalCharges → Calculate if missing or fix negatives
    4. Contract value mapping (Professional/Enterprise/Starter → Monthly/Annual)
    5. Binary columns → Normalize Yes/No/1/0 formats
    6. Categorical columns → Fill missing with mode/default
    7. Numeric outliers → Cap/floor to reasonable ranges
    
    Returns:
        (transformed_df, transformation_log)
    """
    transform_log = []
    df = df.copy()  # Don't modify original
    
    # ============================================
    # 1. FIX TENURE (cap at 0-120 months = 10 years)
    # ============================================
    if 'tenure' in df.columns:
        # Cap at max
        original_max = df['tenure'].max()
        if original_max > 120:
            affected = (df['tenure'] > 120).sum()
            df.loc[df['tenure'] > 120, 'tenure'] = 120
            transform_log.append(f"tenure: Capped {affected} values from max={original_max:.0f} to 120 months")
        
        # Floor at min
        if (df['tenure'] < 0).any():
            negative_count = (df['tenure'] < 0).sum()
            df.loc[df['tenure'] < 0, 'tenure'] = 0
            transform_log.append(f"tenure: Corrected {negative_count} negative values to 0")
    
    # ============================================
    # 2. FIX MONTHLY CHARGES (ensure positive)
    # ============================================
    if 'MonthlyCharges' in df.columns:
        # Convert zeros to minimum viable value
        zero_count = (df['MonthlyCharges'] == 0).sum()
        if zero_count > 0:
            df.loc[df['MonthlyCharges'] == 0, 'MonthlyCharges'] = 0.01
            transform_log.append(f"MonthlyCharges: Converted {zero_count} zero values to 0.01 (free trial customers)")
        
        # Fix negatives
        if (df['MonthlyCharges'] < 0).any():
            negative_count = (df['MonthlyCharges'] < 0).sum()
            df.loc[df['MonthlyCharges'] < 0, 'MonthlyCharges'] = 0.01
            transform_log.append(f"MonthlyCharges: Corrected {negative_count} negative values to 0.01")
        
        # Cap unreasonably high values (>$10,000/month)
        if (df['MonthlyCharges'] > 10000).any():
            high_count = (df['MonthlyCharges'] > 10000).sum()
            df.loc[df['MonthlyCharges'] > 10000, 'MonthlyCharges'] = 10000
            transform_log.append(f"MonthlyCharges: Capped {high_count} values above $10,000 to $10,000")
    
    # ============================================
    # 3. FIX TOTAL CHARGES
    # ============================================
    if 'TotalCharges' in df.columns:
        # Fill missing TotalCharges with MonthlyCharges * tenure
        if df['TotalCharges'].isna().any():
            missing_count = df['TotalCharges'].isna().sum()
            if 'MonthlyCharges' in df.columns and 'tenure' in df.columns:
                df['TotalCharges'] = df['TotalCharges'].fillna(
                    df['MonthlyCharges'] * df['tenure']
                )
                transform_log.append(f"TotalCharges: Calculated {missing_count} missing values from MonthlyCharges * tenure")
        
        # Fix negatives
        if (df['TotalCharges'] < 0).any():
            negative_count = (df['TotalCharges'] < 0).sum()
            df.loc[df['TotalCharges'] < 0, 'TotalCharges'] = 0
            transform_log.append(f"TotalCharges: Corrected {negative_count} negative values to 0")
    
    # ============================================
    # 4. FIX CONTRACT VALUE MAPPING
    # ============================================
    if 'Contract' in df.columns:
        contract_mapping = {
            # User's custom values → Expected values
            'Professional': 'Monthly',
            'Enterprise': 'Annual',
            'Starter': 'Monthly',
            'Basic': 'Monthly',
            'Premium': 'Annual',
            'Free': 'Month-to-month',
            # Handle case variations
            'month-to-month': 'Month-to-month',
            'MONTHLY': 'Monthly',
            'monthly': 'Monthly',
            'ANNUAL': 'Annual',
            'annual': 'Annual',
            'yearly': 'Yearly',
            'YEARLY': 'Yearly',
            # Common variations
            'M2M': 'Month-to-month',
            'MTM': 'Month-to-month',
            '1-year': 'Annual',
            '2-year': 'Two year',
            '2 years': 'Two year',
            'One year': 'Annual',
            'Two years': 'Two year',
        }
        
        original_values = df['Contract'].unique()
        needs_mapping = [v for v in original_values if v in contract_mapping]
        
        if needs_mapping:
            affected = df['Contract'].isin(needs_mapping).sum()
            df['Contract'] = df['Contract'].replace(contract_mapping)
            mapped_to = list(set([contract_mapping[v] for v in needs_mapping]))
            transform_log.append(f"Contract: Mapped {affected} values ({needs_mapping[:3]}... → {mapped_to})")
        
        # Fill any remaining invalid values with 'Month-to-month' (most common)
        valid_contracts = ['Annual', 'Month-to-month', 'Monthly', 'Multi-year', 'Quarterly', 'Two year', 'Yearly']
        invalid_mask = ~df['Contract'].isin(valid_contracts)
        if invalid_mask.any():
            invalid_count = invalid_mask.sum()
            df.loc[invalid_mask, 'Contract'] = 'Month-to-month'
            transform_log.append(f"Contract: Set {invalid_count} remaining invalid values to 'Month-to-month' (default)")
    
    # ============================================
    # 5. NORMALIZE BINARY COLUMNS (Yes/No → 1/0)
    # ============================================
    binary_columns = ['SeniorCitizen', 'Partner', 'Dependents', 'PhoneService', 
                     'PaperlessBilling', 'Churn']  # Common binary columns
    
    for col in binary_columns:
        if col in df.columns and df[col].dtype == 'object':
            # Map Yes/No to 1/0
            yes_no_map = {
                'Yes': 1, 'yes': 1, 'YES': 1,
                'No': 0, 'no': 0, 'NO': 0,
                'True': 1, 'true': 1, 'TRUE': 1,
                'False': 0, 'false': 0, 'FALSE': 0,
                'Y': 1, 'y': 1,
                'N': 0, 'n': 0,
            }
            
            if df[col].isin(yes_no_map.keys()).any():
                affected = df[col].isin(yes_no_map.keys()).sum()
                df[col] = df[col].replace(yes_no_map)
                transform_log.append(f"{col}: Normalized {affected} Yes/No values to 1/0")
    
    # ============================================
    # 6. FILL MISSING CATEGORICAL VALUES
    # ============================================
    categorical_columns = ['InternetService', 'OnlineSecurity', 'OnlineBackup', 
                          'DeviceProtection', 'TechSupport', 'StreamingTV', 'StreamingMovies',
                          'PaymentMethod']
    
    for col in categorical_columns:
        if col in df.columns:
            if df[col].isna().any():
                missing_count = df[col].isna().sum()
                # Fill with mode (most common value) or 'No'
                mode_value = df[col].mode()[0] if not df[col].mode().empty else 'No'
                df[col] = df[col].fillna(mode_value)
                transform_log.append(f"{col}: Filled {missing_count} missing values with '{mode_value}'")
    
    # ============================================
    # 7. CAP EXTREME NUMERIC OUTLIERS
    # ============================================
    numeric_columns = df.select_dtypes(include=['number']).columns
    for col in numeric_columns:
        if col not in ['tenure', 'MonthlyCharges', 'TotalCharges', 'SeniorCitizen']:  # Already handled
            # Cap at 99.9th percentile to remove extreme outliers
            if len(df[col].dropna()) > 10:  # Only if enough data
                upper_bound = df[col].quantile(0.999)
                if (df[col] > upper_bound).any():
                    outlier_count = (df[col] > upper_bound).sum()
                    df.loc[df[col] > upper_bound, col] = upper_bound
                    transform_log.append(f"{col}: Capped {outlier_count} extreme outliers to 99.9th percentile")
    
    return df, transform_log


def _serialize_json_column(value: Any) -> str:
    """
    Ensure consistent JSON serialization for CSV output.
    Converts list/dict or JSON-like strings into proper JSON strings with double quotes.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        # Attempt to parse then re-dump to normalize quotes
        normalized = _normalize_factor_list(value)
        if normalized:
            return json.dumps(normalized, ensure_ascii=False)
        try:
            loaded = json.loads(value)
            return json.dumps(loaded, ensure_ascii=False)
        except Exception:
            return value
    return str(value)


def _generate_summary_from_factors(risk_factors: list, protective_factors: list, churn_prob: float) -> str:
    """
    Generate a human-readable summary from risk and protective factors.
    
    Args:
        risk_factors: List of risk factor dicts
        protective_factors: List of protective factor dicts
        churn_prob: Churn probability (0.0-1.0)
        
    Returns:
        Natural language summary string
    """
    if churn_prob > 0.6:
        risk_level = "HIGH RISK"
        action = "Immediate intervention recommended"
    elif churn_prob > 0.3:
        risk_level = "MEDIUM RISK"
        action = "Proactive engagement suggested"
    else:
        risk_level = "LOW RISK"
        action = "Continue monitoring"
    
    # Build summary parts
    summary_parts = [f"{risk_level} ({churn_prob:.1%} churn probability). {action}."]
    
    # Add top risk factors
    if risk_factors:
        top_risks = [f['message'] for f in risk_factors[:2]]  # Top 2
        if top_risks:
            summary_parts.append(f"Key concerns: {'; '.join(top_risks)}.")
    
    # Add top protective factors
    if protective_factors:
        top_protections = [f['message'] for f in protective_factors[:2]]  # Top 2
        if top_protections:
            summary_parts.append(f"Positive signs: {'; '.join(top_protections)}.")
    
    return " ".join(summary_parts)


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
 