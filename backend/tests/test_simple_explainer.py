"""
Comprehensive tests for Simple Churn Explainer (Task 1.9)

Test Coverage:
- Explainer initialization
- Single customer explanation
- Batch customer explanations
- Feature importance scoring
- Natural language generation
- Risk level classification
- Error handling and fallbacks
- Performance benchmarks

Target: 95%+ code coverage for simple_explainer.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock

from backend.ml.simple_explainer import (
    SimpleChurnExplainer,
    FeatureFactor,
    SimpleExplanation,
    FeatureMapper,
    get_simple_explainer
)
from backend.ml.predict import RetentionPredictor


class TestExplainerInitialization:
    """Test explainer initialization."""
    
    def test_init_with_trained_model(self):
        """Test initialization with trained model."""
        predictor = RetentionPredictor(model_type='saas')
        feature_names = ['tenure', 'MonthlyCharges', 'TotalCharges', 'Contract']
        
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=feature_names
        )
        
        assert explainer.model is not None
        assert len(explainer.importances) > 0
        assert explainer.feature_names == feature_names
    
    def test_init_caching(self):
        """Test explainer is cached for performance."""
        predictor = RetentionPredictor(model_type='saas')
        feature_names = ['tenure', 'MonthlyCharges']
        
        explainer1 = get_simple_explainer(predictor.model, feature_names)
        explainer2 = get_simple_explainer(predictor.model, feature_names)
        
        # Should be same instance (cached)
        assert explainer1 is explainer2


class TestSingleExplanation:
    """Test explanation for single customer."""
    
    def test_explain_high_risk_customer(self):
        """Test explanation for high churn risk customer."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [2],  # Short tenure (risk)
            'MonthlyCharges': [150.0],  # High price (risk)
            'TotalCharges': [300.0],
            'Contract': ['Month-to-month']  # MTM (risk)
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.75,
            top_n=3
        )
        
        # Assertions
        assert result.customer_id == 'TEST_001'
        assert result.churn_probability == 0.75
        assert result.risk_level == 'high'
        assert len(result.top_factors) > 0
        assert result.summary != ""
        assert result.method == 'feature_importance'
        assert result.computation_ms < 100  # Should be very fast
    
    def test_explain_low_risk_customer(self):
        """Test explanation for low churn risk customer."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_002'],
            'tenure': [36],  # Long tenure (protective)
            'MonthlyCharges': [50.0],  # Affordable (protective)
            'TotalCharges': [1800.0],  # High LTV (protective)
            'Contract': ['Annual']  # Annual (protective)
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_002',
            churn_probability=0.15,
            top_n=3
        )
        
        assert result.churn_probability == 0.15
        assert result.risk_level == 'low'
        assert 'low' in result.summary.lower()


class TestBatchExplanations:
    """Test batch explanation generation."""
    
    def test_explain_batch_multiple_customers(self):
        """Test batch explanation for multiple customers."""
        customer_data = pd.DataFrame({
            'customerID': ['C1', 'C2', 'C3', 'C4', 'C5'],
            'tenure': [2, 12, 24, 6, 36],
            'MonthlyCharges': [150, 99, 49, 199, 29],
            'TotalCharges': [300, 1188, 1176, 1194, 1044],
            'Contract': ['Monthly', 'Annual', 'Annual', 'Quarterly', 'Annual']
        })
        
        churn_probs = [0.8, 0.4, 0.2, 0.5, 0.1]
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        results = explainer.explain_batch(
            customer_data=customer_data,
            customer_ids=customer_data['customerID'].tolist(),
            churn_probabilities=churn_probs,
            top_n=3
        )
        
        # Assertions
        assert len(results) == 5
        for result in results:
            assert isinstance(result, SimpleExplanation)
            assert result.customer_id in ['C1', 'C2', 'C3', 'C4', 'C5']
            assert len(result.top_factors) <= 3
            assert result.summary != ""
    
    def test_batch_performance(self):
        """Test batch explanation is fast (<10ms per customer)."""
        # Generate 100 customers
        n_customers = 100
        np.random.seed(42)
        
        customer_data = pd.DataFrame({
            'customerID': [f'C{i}' for i in range(n_customers)],
            'tenure': np.random.randint(1, 60, n_customers),
            'MonthlyCharges': np.random.uniform(20, 500, n_customers),
            'TotalCharges': np.random.uniform(100, 30000, n_customers),
            'Contract': np.random.choice(['Monthly', 'Annual'], n_customers)
        })
        
        churn_probs = np.random.uniform(0.1, 0.9, n_customers).tolist()
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        start = datetime.now()
        results = explainer.explain_batch(
            customer_data=customer_data,
            customer_ids=customer_data['customerID'].tolist(),
            churn_probabilities=churn_probs
        )
        duration = (datetime.now() - start).total_seconds()
        avg_ms = (duration / n_customers) * 1000
        
        # Should be <10ms per customer
        assert avg_ms < 10
        assert len(results) == n_customers


class TestFeatureMapping:
    """Test feature name mapping."""
    
    def test_display_name_mapping(self):
        """Test technical to display name mapping."""
        assert FeatureMapper.get_display_name('tenure') == 'Customer Tenure'
        assert FeatureMapper.get_display_name('MonthlyCharges') == 'Monthly Revenue'
        assert FeatureMapper.get_display_name('feature_usage_score') == 'Feature Adoption'
    
    def test_recommendation_generation(self):
        """Test recommendation based on impact direction."""
        # High risk feature
        rec_high = FeatureMapper.get_recommendation('feature_usage_score', 'increases_risk')
        assert 'feature' in rec_high.lower() or 'adoption' in rec_high.lower()
        
        # Protective feature
        rec_low = FeatureMapper.get_recommendation('feature_usage_score', 'decreases_risk')
        assert rec_low != rec_high


class TestRiskLevelClassification:
    """Test risk level classification."""
    
    def test_risk_levels(self):
        """Test churn probability to risk level mapping."""
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=['tenure', 'MonthlyCharges']
        )
        
        # Test different risk levels
        assert explainer._get_risk_level(0.15) == 'low'
        assert explainer._get_risk_level(0.45) == 'medium'
        assert explainer._get_risk_level(0.70) == 'high'
        assert explainer._get_risk_level(0.90) == 'critical'


class TestExplanationOutput:
    """Test explanation output format."""
    
    def test_explanation_to_dict_format(self):
        """Test SimpleExplanation converts to proper dict format."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.45
        )
        
        result_dict = result.to_dict()
        
        # Check structure
        assert 'customer_id' in result_dict
        assert 'churn_probability' in result_dict
        assert 'risk_level' in result_dict
        assert 'explanation' in result_dict
        assert 'summary' in result_dict['explanation']
        assert 'method' in result_dict['explanation']
        assert 'top_factors' in result_dict['explanation']
        assert 'computation_ms' in result_dict['explanation']
        
        # Check top factors structure
        if result_dict['explanation']['top_factors']:
            factor = result_dict['explanation']['top_factors'][0]
            assert 'feature' in factor
            assert 'impact' in factor
            assert 'current_value' in factor
            assert 'typical_value' in factor
            assert 'recommendation' in factor


class TestNaturalLanguageSummary:
    """Test natural language summary generation."""
    
    def test_summary_includes_risk_level(self):
        """Test summary mentions risk level."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [2],
            'MonthlyCharges': [150.0],
            'TotalCharges': [300.0],
            'Contract': ['Monthly']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.75
        )
        
        # Summary should mention risk
        assert 'risk' in result.summary.lower() or 'high' in result.summary.lower()
    
    def test_summary_includes_factors(self):
        """Test summary mentions top factors."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [2],
            'MonthlyCharges': [150.0],
            'TotalCharges': [300.0],
            'Contract': ['Monthly']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.75
        )
        
        # Summary should be informative (not just "high risk")
        assert len(result.summary) > 50
        assert any(factor.display_name.lower() in result.summary.lower() for factor in result.top_factors)


class TestErrorHandling:
    """Test error handling and fallbacks."""
    
    def test_fallback_explanation_on_error(self):
        """Test fallback explanation when generation fails."""
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=['tenure', 'MonthlyCharges']
        )
        
        # Get fallback
        fallback = explainer._get_fallback_explanation('TEST_001', 0.6)
        
        assert fallback.customer_id == 'TEST_001'
        assert fallback.churn_probability == 0.6
        assert fallback.method == 'fallback'
        assert fallback.metadata.get('fallback') == True
    
    def test_missing_features_handled(self):
        """Test explainer handles missing features gracefully."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0]
            # Missing: TotalCharges, Contract
        })
        
        predictor = RetentionPredictor(model_type='saas')
        # Explainer expects more features than provided
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=['tenure', 'MonthlyCharges', 'TotalCharges', 'Contract', 'seats_used']
        )
        
        # Should not crash
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.5
        )
        
        assert result is not None
        assert result.customer_id == 'TEST_001'


class TestEdgeCases:
    """Test edge cases."""
    
    def test_single_feature(self):
        """Test explanation with single feature."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [12]
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=['tenure']
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.4
        )
        
        assert result is not None
        assert len(result.top_factors) >= 1
    
    def test_zero_churn_probability(self):
        """Test explanation with 0% churn probability."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [48],
            'MonthlyCharges': [99.0],
            'TotalCharges': [4752.0],
            'Contract': ['Annual']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.01  # Very low
        )
        
        assert result.risk_level == 'low'
        assert 'low' in result.summary.lower()
    
    def test_perfect_churn_probability(self):
        """Test explanation with 100% churn probability."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [1],
            'MonthlyCharges': [500.0],
            'TotalCharges': [500.0],
            'Contract': ['Monthly']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.99  # Very high
        )
        
        assert result.risk_level == 'critical'
        assert 'critical' in result.summary.lower() or 'immediate' in result.summary.lower()


class TestPerformanceTargets:
    """Test performance targets are met."""
    
    def test_single_explanation_speed(self):
        """Test single explanation generates in <10ms."""
        customer_data = pd.DataFrame({
            'customerID': ['TEST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        predictor = RetentionPredictor(model_type='saas')
        explainer = SimpleChurnExplainer(
            model=predictor.model,
            feature_names=customer_data.columns.tolist()
        )
        
        result = explainer.explain_prediction(
            customer_data=customer_data,
            customer_id='TEST_001',
            churn_probability=0.5
        )
        
        # Should be <10ms (feature importance is fast!)
        assert result.computation_ms < 10


# ========================================
# PYTEST CONFIGURATION
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--durations=10"])

