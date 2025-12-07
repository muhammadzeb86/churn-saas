"""
Real Data Collector for ML Model Training

Collects actual customer data and churn outcomes for future ML model training.
This is the foundation for training on REAL data (not synthetic).

Purpose:
- Record every prediction with full customer features
- Track actual churn outcomes when they occur
- Build labeled dataset for future ML training
- Enable model performance analysis

Data Flow:
1. Prediction made → Record features + prediction
2. Customer churns (or stays) → Record actual outcome
3. After 100+ outcomes → Have real labeled training data
4. Train ML model on REAL data → Better than any synthetic approach

Author: RetainWise ML Team
Date: December 7, 2025
Version: 1.0
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from backend.api.database import Base, get_async_session
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON

logger = logging.getLogger(__name__)


# ========================================
# DATABASE MODEL
# ========================================

class MLTrainingData(Base):
    """
    Stores predictions and actual outcomes for ML training.
    
    This table builds our REAL labeled dataset over time.
    """
    __tablename__ = "ml_training_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Customer info
    customer_id = Column(String(100), nullable=False, index=True)
    prediction_id = Column(String(100), nullable=True, index=True)
    
    # Features (at time of prediction)
    features_json = Column(JSON, nullable=False)
    
    # Prediction results
    predicted_churn_prob = Column(Float, nullable=False)
    predicted_retention_prob = Column(Float, nullable=False)
    model_type = Column(String(50), nullable=False)  # 'telecom', 'saas_baseline', etc.
    experiment_group = Column(String(20), nullable=True)  # 'control', 'treatment'
    
    # Actual outcome (filled in later)
    actual_churned = Column(Boolean, nullable=True)  # True = churned, False = retained
    outcome_recorded_at = Column(DateTime, nullable=True)
    days_to_outcome = Column(Integer, nullable=True)  # Days from prediction to outcome
    
    # Timestamps
    predicted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ========================================
# DATA COLLECTOR
# ========================================

class RealDataCollector:
    """
    Collects real customer data and outcomes for ML training.
    
    Usage:
        collector = RealDataCollector()
        
        # When prediction is made
        await collector.record_prediction(customer_data, prediction_result)
        
        # When customer churns (detected by system)
        await collector.record_churn_outcome(customer_id, churned=True)
        
        # Export for training (after 100+ outcomes)
        training_data = await collector.export_training_data()
    """
    
    async def record_prediction(
        self,
        customer_data: Dict[str, Any],
        prediction_result: Dict[str, Any],
        prediction_id: Optional[str] = None
    ) -> None:
        """
        Record a prediction with all features for future training.
        
        Args:
            customer_data: Dict with customer features
            prediction_result: Dict with prediction results
            prediction_id: Optional prediction ID from database
        """
        try:
            async with get_async_session() as db:
                # Create record
                record = MLTrainingData(
                    customer_id=customer_data.get('customerID', 'unknown'),
                    prediction_id=prediction_id,
                    features_json=customer_data,
                    predicted_churn_prob=prediction_result.get('churn_probability', 0.0),
                    predicted_retention_prob=prediction_result.get('retention_probability', 1.0),
                    model_type=prediction_result.get('model_type', 'unknown'),
                    experiment_group=prediction_result.get('experiment_group'),
                    predicted_at=datetime.utcnow()
                )
                
                db.add(record)
                await db.commit()
                
                logger.info(
                    f"Recorded prediction for customer {customer_data.get('customerID')}",
                    extra={
                        'event': 'prediction_recorded',
                        'customer_id': customer_data.get('customerID'),
                        'model_type': prediction_result.get('model_type'),
                        'churn_prob': prediction_result.get('churn_probability')
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to record prediction: {e}")
            # Don't fail prediction if logging fails
    
    async def record_churn_outcome(
        self,
        customer_id: str,
        churned: bool,
        churn_date: Optional[datetime] = None
    ) -> None:
        """
        Record actual churn outcome when known.
        
        This is called when:
        - Customer cancels subscription (churned=True)
        - Customer reaches milestone (3/6/12 months active, churned=False)
        
        Args:
            customer_id: Customer identifier
            churned: True if customer churned, False if retained
            churn_date: Optional date of churn
        """
        try:
            async with get_async_session() as db:
                # Find most recent prediction for this customer
                stmt = select(MLTrainingData).where(
                    MLTrainingData.customer_id == customer_id,
                    MLTrainingData.actual_churned == None  # Not yet recorded
                ).order_by(MLTrainingData.predicted_at.desc())
                
                result = await db.execute(stmt)
                record = result.scalars().first()
                
                if record:
                    # Calculate days from prediction to outcome
                    outcome_date = churn_date or datetime.utcnow()
                    days_to_outcome = (outcome_date - record.predicted_at).days
                    
                    # Update with actual outcome
                    record.actual_churned = churned
                    record.outcome_recorded_at = datetime.utcnow()
                    record.days_to_outcome = days_to_outcome
                    
                    await db.commit()
                    
                    logger.info(
                        f"Recorded churn outcome for customer {customer_id}",
                        extra={
                            'event': 'outcome_recorded',
                            'customer_id': customer_id,
                            'churned': churned,
                            'days_to_outcome': days_to_outcome,
                            'predicted_churn_prob': record.predicted_churn_prob
                        }
                    )
                else:
                    logger.warning(f"No prediction found for customer {customer_id}")
                    
        except Exception as e:
            logger.error(f"Failed to record churn outcome: {e}")
    
    async def export_training_data(
        self,
        min_outcomes: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Export real labeled data for ML training.
        
        Only exports data where actual outcome is known.
        
        Args:
            min_outcomes: Minimum number of outcomes required
            
        Returns:
            DataFrame with features + labels, or None if insufficient data
        """
        try:
            async with get_async_session() as db:
                # Get all records with actual outcomes
                stmt = select(MLTrainingData).where(
                    MLTrainingData.actual_churned != None
                )
                
                result = await db.execute(stmt)
                records = result.scalars().all()
                
                if len(records) < min_outcomes:
                    logger.warning(
                        f"Insufficient training data: {len(records)} outcomes "
                        f"(need {min_outcomes} minimum)"
                    )
                    return None
                
                # Convert to DataFrame
                data = []
                for record in records:
                    row = record.features_json.copy()
                    row['Churn'] = 1 if record.actual_churned else 0
                    row['predicted_churn_prob'] = record.predicted_churn_prob
                    row['model_type_used'] = record.model_type
                    row['experiment_group'] = record.experiment_group
                    data.append(row)
                
                df = pd.DataFrame(data)
                
                logger.info(
                    f"Exported {len(df)} real labeled samples for training",
                    extra={
                        'event': 'training_data_exported',
                        'n_samples': len(df),
                        'churn_rate': df['Churn'].mean(),
                        'date_range_days': (
                            records[-1].predicted_at - records[0].predicted_at
                        ).days
                    }
                )
                
                return df
                
        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            return None
    
    async def get_experiment_statistics(self) -> Dict[str, Any]:
        """
        Get A/B test statistics for analysis.
        
        Returns:
            Dict with experiment metrics
        """
        try:
            async with get_async_session() as db:
                # Get all records with outcomes
                stmt = select(MLTrainingData).where(
                    MLTrainingData.actual_churned != None
                )
                
                result = await db.execute(stmt)
                records = result.scalars().all()
                
                if not records:
                    return {'status': 'no_data', 'n_outcomes': 0}
                
                # Split by experiment group
                control = [r for r in records if r.experiment_group == 'control']
                treatment = [r for r in records if r.experiment_group == 'treatment']
                
                # Calculate metrics for each group
                def calculate_metrics(group):
                    if not group:
                        return None
                    
                    actual_churn_rate = sum(1 for r in group if r.actual_churned) / len(group)
                    avg_predicted_prob = sum(r.predicted_churn_prob for r in group) / len(group)
                    
                    # Calculate prediction accuracy
                    correct = sum(
                        1 for r in group 
                        if (r.predicted_churn_prob > 0.5 and r.actual_churned) or
                           (r.predicted_churn_prob <= 0.5 and not r.actual_churned)
                    )
                    accuracy = correct / len(group)
                    
                    return {
                        'n_predictions': len(group),
                        'actual_churn_rate': actual_churn_rate,
                        'avg_predicted_churn_prob': avg_predicted_prob,
                        'accuracy': accuracy
                    }
                
                stats = {
                    'total_outcomes': len(records),
                    'control_group': calculate_metrics(control),
                    'treatment_group': calculate_metrics(treatment),
                    'data_collection_days': (
                        records[-1].predicted_at - records[0].predicted_at
                    ).days if len(records) > 1 else 0
                }
                
                logger.info(f"Experiment statistics: {stats}")
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get experiment statistics: {e}")
            return {'status': 'error', 'error': str(e)}


# ========================================
# SINGLETON INSTANCE
# ========================================

_collector_instance: Optional[RealDataCollector] = None

def get_data_collector() -> RealDataCollector:
    """
    Get singleton instance of data collector.
    
    Returns:
        RealDataCollector instance
    """
    global _collector_instance
    
    if _collector_instance is None:
        _collector_instance = RealDataCollector()
    
    return _collector_instance

