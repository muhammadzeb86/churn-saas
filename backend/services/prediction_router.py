"""
Prediction Router for A/B Testing

Routes predictions between different models for comparison and validation.
Logs all predictions for future analysis and model improvement.

Models:
- Control: Current Telecom model with feature alignment (76% accuracy baseline)
- Treatment: New SaaS baseline model (business rules, interpretable)

Purpose:
- Validate SaaS baseline against production Telecom model
- Collect real customer outcomes for future ML training
- Data-driven decision making (not assumptions)

Author: RetainWise ML Team
Date: December 7, 2025
Version: 1.0
"""

import pandas as pd
import numpy as np
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from backend.ml.predict import RetentionPredictor
from backend.ml.saas_baseline import SaaSChurnBaseline

logger = logging.getLogger(__name__)


class PredictionRouter:
    """
    A/B testing router for churn predictions.
    
    Features:
    - Consistent routing (same customer always gets same model)
    - Configurable traffic split
    - Comprehensive logging
    - Graceful fallbacks
    - Compatible with existing prediction service
    
    Usage:
        router = PredictionRouter()
        prediction = router.route_prediction(customer_data)
        # Automatically handles A/B assignment and logging
    """
    
    def __init__(
        self, 
        treatment_percentage: float = 0.50,
        enable_logging: bool = True
    ):
        """
        Initialize prediction router.
        
        Args:
            treatment_percentage: % traffic to treatment group (0.0-1.0)
            enable_logging: Whether to log predictions for analysis
        """
        self.treatment_percentage = treatment_percentage
        self.enable_logging = enable_logging
        
        # Initialize models
        try:
            self.telecom_model = RetentionPredictor(model_type='telecom')
            logger.info("✅ Loaded Telecom model (control group)")
        except Exception as e:
            logger.error(f"Failed to load Telecom model: {e}")
            self.telecom_model = None
        
        try:
            self.saas_baseline = SaaSChurnBaseline()
            logger.info("✅ Loaded SaaS baseline (treatment group)")
        except Exception as e:
            logger.error(f"Failed to load SaaS baseline: {e}")
            self.saas_baseline = None
        
        if not self.telecom_model and not self.saas_baseline:
            raise RuntimeError("No models available - cannot initialize router")
        
        logger.info(f"Prediction router initialized: {treatment_percentage:.0%} traffic to treatment")
    
    def assign_experiment_group(self, customer_id: str) -> str:
        """
        Assign customer to experiment group (control or treatment).
        
        Uses consistent hashing - same customer always gets same group.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            'control' or 'treatment'
        """
        # Hash customer ID to get deterministic group assignment
        hash_value = int(hashlib.md5(customer_id.encode()).hexdigest(), 16)
        assignment_value = (hash_value % 100) / 100.0
        
        if assignment_value < self.treatment_percentage:
            return 'treatment'
        else:
            return 'control'
    
    def route_prediction(
        self, 
        customer_data: pd.DataFrame,
        force_group: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route prediction to appropriate model based on A/B assignment.
        
        Args:
            customer_data: DataFrame with customer features (single row or batch)
            force_group: Force specific group ('control', 'treatment', or None for A/B)
            
        Returns:
            Dict with prediction results and metadata
        """
        # Handle single row vs batch
        is_single = len(customer_data) == 1
        
        if is_single:
            customer_id = customer_data.iloc[0].get('customerID', 'unknown')
        else:
            customer_id = 'batch'
        
        # Assign experiment group
        if force_group:
            experiment_group = force_group
        else:
            experiment_group = self.assign_experiment_group(customer_id)
        
        logger.info(f"Routing prediction: customer={customer_id}, group={experiment_group}")
        
        # Route to appropriate model
        try:
            if experiment_group == 'treatment' and self.saas_baseline:
                prediction = self._predict_with_saas_baseline(customer_data)
                model_used = 'saas_baseline'
            elif self.telecom_model:
                prediction = self._predict_with_telecom(customer_data)
                model_used = 'telecom_aligned'
            elif self.saas_baseline:
                # Fallback to treatment if control unavailable
                prediction = self._predict_with_saas_baseline(customer_data)
                model_used = 'saas_baseline_fallback'
            else:
                raise RuntimeError("No models available")
            
            # Add experiment metadata
            prediction['experiment_group'] = experiment_group
            prediction['model_used'] = model_used
            prediction['router_version'] = '1.0'
            
            return prediction
            
        except Exception as e:
            logger.error(f"Prediction routing failed: {e}")
            
            # Fallback strategy
            if self.saas_baseline:
                logger.warning("Falling back to SaaS baseline")
                prediction = self._predict_with_saas_baseline(customer_data)
                prediction['experiment_group'] = 'fallback'
                prediction['model_used'] = 'saas_baseline_fallback'
            elif self.telecom_model:
                logger.warning("Falling back to Telecom model")
                prediction = self._predict_with_telecom(customer_data)
                prediction['experiment_group'] = 'fallback'
                prediction['model_used'] = 'telecom_fallback'
            else:
                raise
            
            return prediction
    
    def _predict_with_saas_baseline(self, customer_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Get prediction from SaaS baseline model.
        
        Args:
            customer_data: DataFrame with customer features
            
        Returns:
            Dict with prediction results
        """
        # SaaS baseline returns DataFrame with predictions
        predictions_df = self.saas_baseline.predict(customer_data)
        
        # Convert to dict format (for single row)
        if len(predictions_df) == 1:
            return predictions_df.iloc[0].to_dict()
        else:
            return {'predictions': predictions_df.to_dict('records')}
    
    def _predict_with_telecom(self, customer_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Get prediction from Telecom model (with feature alignment).
        
        Args:
            customer_data: DataFrame with customer features
            
        Returns:
            Dict with prediction results
        """
        # Telecom model uses existing predict method
        predictions_df = self.telecom_model.predict(customer_data)
        
        # Convert to dict format
        if len(predictions_df) == 1:
            return predictions_df.iloc[0].to_dict()
        else:
            return {'predictions': predictions_df.to_dict('records')}


# ========================================
# SINGLETON INSTANCE
# ========================================

_router_instance: Optional[PredictionRouter] = None

def get_prediction_router() -> PredictionRouter:
    """
    Get singleton instance of prediction router.
    
    Returns:
        PredictionRouter instance
    """
    global _router_instance
    
    if _router_instance is None:
        _router_instance = PredictionRouter()
    
    return _router_instance

