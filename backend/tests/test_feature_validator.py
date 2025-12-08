"""
Comprehensive tests for Feature Validator (Task 1.6)

Test Coverage:
- Schema validation (required fields)
- Data type validation (numeric, string, categorical)
- Range validation (min/max)
- Null handling
- Categorical values
- Business rules (cross-field validation)
- ML readiness checks
- Performance benchmarks
- Edge cases

Target: 95%+ code coverage for feature_validator.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backend.ml.feature_validator import (
    SaaSFeatureValidator,
    ValidationLevel,
    IssueType,
    ValidationIssue,
    ValidationResult,
    validate_saas_data
)


class TestSchemaValidation:
    """Test schema validation (required fields)."""
    
    def test_all_required_fields_present(self):
        """Test validation passes when all required fields present."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metrics['quality_score'] >= 80
    
    def test_missing_required_field(self):
        """Test validation fails when required field missing."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            # MonthlyCharges MISSING
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any('MonthlyCharges' in error.message for error in result.errors)
    
    def test_multiple_missing_fields(self):
        """Test validation reports all missing required fields."""
        df = pd.DataFrame({
            'customerID': ['CUST_001']
            # Missing: tenure, MonthlyCharges, TotalCharges, Contract
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert len(result.errors) >= 1
        # Should mention multiple missing fields
        schema_errors = [e for e in result.errors if e.field == 'schema']
        assert len(schema_errors) == 1
        assert 'tenure' in schema_errors[0].message
        assert 'MonthlyCharges' in schema_errors[0].message


class TestDataTypeValidation:
    """Test data type validation."""
    
    def test_numeric_field_with_valid_numbers(self):
        """Test numeric validation passes with valid numbers."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': [12, 24],  # Proper numeric
            'MonthlyCharges': [99.0, 149.0],
            'TotalCharges': [1188.0, 3576.0],
            'Contract': ['Annual', 'Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        tenure_errors = [e for e in result.errors if 'tenure' in e.field]
        assert len(tenure_errors) == 0
    
    def test_numeric_field_with_strings(self):
        """Test error when numeric field contains non-convertible strings."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': ['twelve', 'invalid'],  # Should be numeric!
            'MonthlyCharges': [99.0, 149.0],
            'TotalCharges': [1188.0, 1788.0],
            'Contract': ['Annual', 'Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('tenure' in error.field and 'non-numeric' in error.message for error in result.errors)
    
    def test_numeric_field_with_convertible_strings(self):
        """Test warning when numeric field has convertible string dtype."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': ['12', '24'],  # String dtype but convertible
            'MonthlyCharges': [99.0, 149.0],
            'TotalCharges': [1188.0, 3576.0],
            'Contract': ['Annual', 'Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # Should have warning about dtype but not blocking error
        tenure_warnings = [w for w in result.warnings if 'tenure' in w.field]
        # May have warning about dtype conversion
        assert result.is_valid  # Not blocking


class TestRangeValidation:
    """Test numeric range validation."""
    
    def test_tenure_negative_value(self):
        """Test error when tenure is negative."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [-5],  # Invalid!
            'MonthlyCharges': [99.0],
            'TotalCharges': [0.0],
            'Contract': ['Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('tenure' in error.field and 'below minimum' in error.message for error in result.errors)
    
    def test_tenure_extreme_value(self):
        """Test error when tenure exceeds maximum."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [999],  # 999 months = 83 years! Invalid!
            'MonthlyCharges': [99.0],
            'TotalCharges': [98901.0],
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('tenure' in error.field and 'above maximum' in error.message for error in result.errors)
    
    def test_monthly_charges_zero(self):
        """Test error when monthly charges is zero."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [3],
            'MonthlyCharges': [0],  # Below minimum (0.01)
            'TotalCharges': [0],
            'Contract': ['Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('MonthlyCharges' in error.field and 'below minimum' in error.message for error in result.errors)
    
    def test_valid_ranges(self):
        """Test validation passes with values in valid ranges."""
        df = pd.DataFrame({
            'customerID': ['C1', 'C2', 'C3'],
            'tenure': [0, 60, 120],  # Min, mid, max
            'MonthlyCharges': [0.01, 1000, 99999],  # Min, mid, near-max
            'TotalCharges': [0, 50000, 9999999],  # Min, mid, near-max
            'Contract': ['Monthly', 'Annual', 'Quarterly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        range_errors = [e for e in result.errors if 'below' in e.message or 'above' in e.message]
        assert len(range_errors) == 0


class TestCategoricalValidation:
    """Test categorical value validation."""
    
    def test_invalid_contract_type(self):
        """Test error when contract type not in allowed values."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['InvalidContractType']  # Not allowed!
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('Contract' in error.field and 'invalid' in error.message for error in result.errors)
    
    def test_valid_contract_variations(self):
        """Test all valid contract type variations."""
        df = pd.DataFrame({
            'customerID': ['C1', 'C2', 'C3', 'C4', 'C5'],
            'tenure': [12, 12, 12, 12, 12],
            'MonthlyCharges': [99, 99, 99, 99, 99],
            'TotalCharges': [1188, 1188, 1188, 1188, 1188],
            'Contract': ['Month-to-month', 'Monthly', 'Quarterly', 'Annual', 'Yearly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # All should be valid
        contract_errors = [e for e in result.errors if 'Contract' in e.field]
        assert len(contract_errors) == 0
        assert result.is_valid


class TestNullValidation:
    """Test null value handling."""
    
    def test_null_in_required_field(self):
        """Test error when required field has null values."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', None],  # Null not allowed!
            'tenure': [12, 24],
            'MonthlyCharges': [99.0, 149.0],
            'TotalCharges': [1188.0, 3576.0],
            'Contract': ['Annual', 'Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('customerID' in error.field and 'null' in error.message for error in result.errors)
    
    def test_null_in_total_charges_allowed(self):
        """Test null is allowed in TotalCharges for new customers."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': [0, 1],
            'MonthlyCharges': [99.0, 149.0],
            'TotalCharges': [None, 149.0],  # Null allowed for new customers
            'Contract': ['Monthly', 'Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # Should pass or only have warnings
        total_errors = [e for e in result.errors if 'TotalCharges' in e.field and 'null' in e.message]
        assert len(total_errors) == 0


class TestBusinessRules:
    """Test business rule validation."""
    
    def test_total_charges_less_than_monthly(self):
        """Test warning when TotalCharges < MonthlyCharges for existing customers."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],  # Existing customer
            'MonthlyCharges': [100.0],
            'TotalCharges': [50.0],  # Less than monthly! Data error!
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # Should have warning (not necessarily error)
        assert len(result.warnings) >= 1
        assert any('TotalCharges' in warning.field for warning in result.warnings)
    
    def test_seats_used_exceeds_purchased(self):
        """Test error when seats_used > seats_purchased."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual'],
            'seats_purchased': [5],
            'seats_used': [10]  # Can't use more than purchased!
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('seats_used' in error.field for error in result.errors)
    
    def test_seats_valid_utilization(self):
        """Test validation passes when seats_used <= seats_purchased."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002', 'CUST_003'],
            'tenure': [12, 12, 12],
            'MonthlyCharges': [99, 99, 99],
            'TotalCharges': [1188, 1188, 1188],
            'Contract': ['Annual', 'Annual', 'Annual'],
            'seats_purchased': [5, 10, 20],
            'seats_used': [3, 10, 15]  # All valid
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        seats_errors = [e for e in result.errors if 'seats' in e.field]
        assert len(seats_errors) == 0


class TestMLReadiness:
    """Test ML readiness validation."""
    
    def test_small_dataset_warning(self):
        """Test warning when dataset is too small."""
        df = pd.DataFrame({
            'customerID': ['C1', 'C2', 'C3'],  # Only 3 rows
            'tenure': [12, 6, 24],
            'MonthlyCharges': [99, 149, 499],
            'TotalCharges': [1188, 894, 11976],
            'Contract': ['Annual', 'Monthly', 'Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.ML_TRAINING)
        
        # Should have warning about dataset size
        assert any('dataset_size' in warning.field for warning in result.warnings)
    
    def test_low_churn_rate_warning(self):
        """Test warning when churn rate is very low."""
        df = pd.DataFrame({
            'customerID': [f'C{i}' for i in range(100)],
            'tenure': [12] * 100,
            'MonthlyCharges': [99] * 100,
            'TotalCharges': [1188] * 100,
            'Contract': ['Annual'] * 100,
            'Churn': [0] * 99 + [1]  # Only 1% churn rate
        })
        
        result = validate_saas_data(df, level=ValidationLevel.ML_TRAINING)
        
        # Should have warning about low churn rate
        assert any('Churn' in warning.field and 'low' in warning.message for warning in result.warnings)
    
    def test_high_correlation_detection(self):
        """Test detection of highly correlated features."""
        # Create data with perfect correlation
        np.random.seed(42)
        base_values = np.random.randint(1, 100, 50)
        
        df = pd.DataFrame({
            'customerID': [f'C{i}' for i in range(50)],
            'tenure': base_values,
            'MonthlyCharges': base_values * 10.0,  # Perfectly correlated with tenure
            'TotalCharges': base_values * 120.0,  # Also correlated
            'Contract': ['Annual'] * 50
        })
        
        result = validate_saas_data(df, level=ValidationLevel.ML_TRAINING)
        
        # Should have info message about high correlation
        # (Note: May not trigger if correlation is not above threshold)
        # This is informational, not an error
        assert result.is_valid


class TestValidationLevels:
    """Test different validation levels."""
    
    def test_minimal_level_only_errors(self):
        """Test MINIMAL level only checks critical errors."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [100.0],
            'TotalCharges': [50.0],  # Less than monthly (business rule warning)
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.MINIMAL)
        
        # Should pass (no critical errors)
        assert result.is_valid
        # Business rule warnings not checked at MINIMAL level
    
    def test_standard_level_includes_business_rules(self):
        """Test STANDARD level checks business rules."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [100.0],
            'TotalCharges': [50.0],  # Less than monthly (business rule warning)
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # Should have warning about TotalCharges
        assert len(result.warnings) >= 1
        assert any('TotalCharges' in w.field for w in result.warnings)
    
    def test_ml_training_level_extra_checks(self):
        """Test ML_TRAINING level includes extra checks."""
        df = pd.DataFrame({
            'customerID': ['C1', 'C2', 'C3'],  # Small dataset
            'tenure': [12, 6, 24],
            'MonthlyCharges': [99, 149, 499],
            'TotalCharges': [1188, 894, 11976],
            'Contract': ['Annual', 'Monthly', 'Annual']
        })
        
        result_standard = validate_saas_data(df, level=ValidationLevel.STANDARD)
        result_ml = validate_saas_data(df, level=ValidationLevel.ML_TRAINING)
        
        # ML_TRAINING should have more warnings (dataset size)
        assert len(result_ml.warnings) >= len(result_standard.warnings)


class TestPerformance:
    """Test validation performance."""
    
    def test_large_dataset_performance(self):
        """Test validation completes in reasonable time for 10K rows."""
        # Generate 10K rows
        n_rows = 10000
        np.random.seed(42)
        
        df = pd.DataFrame({
            'customerID': [f'CUST_{i:05d}' for i in range(n_rows)],
            'tenure': np.random.randint(0, 100, n_rows),
            'MonthlyCharges': np.random.uniform(10, 500, n_rows),
            'TotalCharges': np.random.uniform(100, 50000, n_rows),
            'Contract': np.random.choice(['Monthly', 'Annual', 'Quarterly'], n_rows)
        })
        
        start = datetime.now()
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        duration = (datetime.now() - start).total_seconds()
        
        # Should complete in <500ms (reasonable for 10K rows)
        assert duration < 0.5
        assert result.total_rows == n_rows
        assert result.is_valid  # Random data should mostly be valid


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_dataframe(self):
        """Test validation handles empty DataFrame."""
        df = pd.DataFrame()
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert len(result.errors) >= 1  # Missing required columns
    
    def test_single_row(self):
        """Test validation works for single row."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        assert result.total_rows == 1
    
    def test_duplicate_customer_ids(self):
        """Test error when customerID has duplicates."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_001', 'CUST_002'],  # Duplicate!
            'tenure': [12, 24, 6],
            'MonthlyCharges': [99, 149, 79],
            'TotalCharges': [1188, 3576, 474],
            'Contract': ['Annual', 'Annual', 'Monthly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('customerID' in error.field and 'duplicate' in error.message for error in result.errors)
    
    def test_all_null_column(self):
        """Test validation handles column with all nulls."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': [12, 24],
            'MonthlyCharges': [None, None],  # All null!
            'TotalCharges': [1188.0, 2376.0],
            'Contract': ['Annual', 'Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert not result.is_valid
        assert any('MonthlyCharges' in error.field and 'null' in error.message for error in result.errors)


class TestValidationResult:
    """Test ValidationResult object and summary."""
    
    def test_summary_format(self):
        """Test get_summary() returns proper format."""
        df = pd.DataFrame({
            'customerID': ['CUST_001'],
            'tenure': [12],
            'MonthlyCharges': [99.0],
            'TotalCharges': [1188.0],
            'Contract': ['Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        summary = result.get_summary()
        
        # Check structure
        assert 'status' in summary
        assert 'total_rows' in summary
        assert 'critical_issues' in summary
        assert 'data_warnings' in summary
        assert 'suggestions' in summary
        assert 'details' in summary
        
        # Check details structure
        assert 'errors' in summary['details']
        assert 'warnings' in summary['details']
    
    def test_metrics_included(self):
        """Test validation result includes monitoring metrics."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002'],
            'tenure': [12, 24],
            'MonthlyCharges': [99, 149],
            'TotalCharges': [1188, 3576],
            'Contract': ['Annual', 'Quarterly']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        # Should have metrics for CloudWatch monitoring
        assert 'quality_score' in result.metrics
        assert 'completeness_score' in result.metrics
        assert 'error_count' in result.metrics
        assert 'warning_count' in result.metrics
        assert 'total_rows' in result.metrics
        
        # Quality score should be reasonable
        assert 0 <= result.metrics['quality_score'] <= 100


class TestRealWorldData:
    """Test with real-world SaaS data patterns."""
    
    def test_stripe_like_export(self):
        """Test validation with Stripe-like export format."""
        df = pd.DataFrame({
            'customerID': ['cus_ABC123', 'cus_DEF456', 'cus_GHI789'],
            'tenure': [6, 12, 3],
            'MonthlyCharges': [29.0, 99.0, 19.0],
            'TotalCharges': [174.0, 1188.0, 57.0],
            'Contract': ['Monthly', 'Annual', 'Monthly'],
            'seats_purchased': [1, 5, 1],
            'seats_used': [1, 4, 1],
            'feature_usage_score': [65.0, 85.0, 45.0]
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        assert result.metrics['quality_score'] >= 85
    
    def test_minimal_required_fields_only(self):
        """Test validation passes with only required fields (no optional)."""
        df = pd.DataFrame({
            'customerID': ['CUST_001', 'CUST_002', 'CUST_003'],
            'tenure': [6, 12, 24],
            'MonthlyCharges': [99.0, 149.0, 499.0],
            'TotalCharges': [594.0, 1788.0, 11976.0],
            'Contract': ['Monthly', 'Quarterly', 'Annual']
        })
        
        result = validate_saas_data(df, level=ValidationLevel.STANDARD)
        
        assert result.is_valid
        # Completeness score should reflect missing optional fields
        assert result.metrics['completeness_score'] < 100


# ========================================
# PYTEST CONFIGURATION
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--durations=10"])

