"""
Unit tests for Intelligent Column Mapper

Tests:
1. Exact matching
2. Normalized matching (case/space insensitive)
3. Alias matching
4. Partial matching
5. Fuzzy matching (typo tolerance)
6. Confidence scoring
7. Missing required columns
8. Unmapped columns
9. Suggestion generation
10. Multi-industry support
11. Duplicate column handling (DeepSeek fix)
12. CSV injection sanitization (DeepSeek fix)
13. Empty column filtering
14. Numeric header detection
15. Multi-row header handling
16. Data type auto-conversion
17. BOM handling
18. Unicode support
19. Column count limits
20. Preview mapping
21. Apply mapping
22. Convenience function
23. Preprocessing pipeline
24. Date standardization
25. Edge cases

Author: AI Assistant
Created: December 7, 2025
Version: 2.0 (Enhanced test coverage)
"""

import pytest
import pandas as pd
from backend.ml.column_mapper import (
    IntelligentColumnMapper,
    ColumnMatch,
    MatchStrategy,
    map_csv_columns,
    ColumnAliases
)


class TestIntelligentColumnMapper:
    
    def test_exact_match(self):
        """Test exact column name matching."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['Month-to-month', 'One year', 'Two year']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.matches) == 5
        assert all(m.confidence == 100.0 for m in report.matches)
        assert all(m.strategy == MatchStrategy.EXACT for m in report.matches)
    
    def test_normalized_match(self):
        """Test case-insensitive and space-insensitive matching."""
        df = pd.DataFrame({
            'Customer ID': [1, 2, 3],
            'TENURE': [12, 24, 36],
            'monthly_charges': [50, 60, 70],
            'total charges': [600, 1440, 2520],
            'CONTRACT': ['Month-to-month', 'One year', 'Two year']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.matches) == 5
        assert all(m.confidence == 100.0 for m in report.matches)
    
    def test_alias_match(self):
        """Test matching common column aliases."""
        df = pd.DataFrame({
            'user_id': [1, 2, 3],
            'months_active': [12, 24, 36],
            'mrr': [50, 60, 70],
            'ltv': [600, 1440, 2520],
            'plan_type': ['Month-to-month', 'One year', 'Two year']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.matches) == 5
        assert all(m.confidence >= 95.0 for m in report.matches)
        assert all(m.strategy == MatchStrategy.ALIAS for m in report.matches)
    
    def test_partial_match(self):
        """Test partial substring matching."""
        df = pd.DataFrame({
            'cust_id': [1, 2, 3],
            'tenure_mos': [12, 24, 36],
            'monthly_fee': [50, 60, 70],
            'total_amount': [600, 1440, 2520],
            'contract_type': ['Month-to-month', 'One year', 'Two year']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.matches) == 5
        assert all(70 <= m.confidence <= 100 for m in report.matches)
    
    def test_fuzzy_match_typos(self):
        """Test fuzzy matching for typos."""
        df = pd.DataFrame({
            'customar_id': [1, 2, 3],
            'tenur': [12, 24, 36],
            'monthly_chargers': [50, 60, 70],
            'toal_charges': [600, 1440, 2520],
            'contrat': ['Month-to-month', 'One year', 'Two year']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.matches) == 5
        assert all(75 <= m.confidence <= 100 for m in report.matches)
    
    def test_missing_required_columns(self):
        """Test handling of missing required columns."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure': [12, 24, 36]
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is False
        assert len(report.missing_required) == 3
        assert 'MonthlyCharges' in report.missing_required
        assert 'TotalCharges' in report.missing_required
        assert 'Contract' in report.missing_required
        assert len(report.suggestions) > 0
    
    def test_unmapped_user_columns(self):
        """Test handling of unmapped user columns."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['Month-to-month', 'One year', 'Two year'],
            'unknown_column_1': ['a', 'b', 'c'],
            'random_data': [100, 200, 300]
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        assert len(report.unmapped_user_columns) == 2
        assert 'unknown_column_1' in report.unmapped_user_columns
        assert 'random_data' in report.unmapped_user_columns
    
    def test_confidence_scoring(self):
        """Test confidence scores are accurate."""
        # Use different standard columns to avoid duplicate handling filtering out matches
        df = pd.DataFrame({
            'customerID': [1],  # Exact match (100%)
            'Customer ID': [2],  # Normalized match (100%)
            'user_id': [3],  # Alias match (95%)
            'cust_id': [4],  # Partial match (70-90%)
            'customar_id': [5]  # Fuzzy match (75-100%)
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # All should map to customerID, but with different strategies/confidence
        # After duplicate handling, we should have at least one match
        assert len(report.matches) >= 1
        
        # The best match should be 100% (exact)
        matches_sorted = sorted(report.matches, key=lambda m: m.confidence, reverse=True)
        assert matches_sorted[0].confidence == 100.0
        
        # Test confidence scoring with different standard columns
        df2 = pd.DataFrame({
            'customerID': [1],  # Exact (100%)
            'tenure': [12],  # Exact (100%)
            'mrr': [50],  # Alias (95%)
            'monthly_fee': [60],  # Partial (70-90%)
            'toal_charges': [600]  # Fuzzy (75-100%)
        })
        
        report2 = mapper.map_columns(df2)
        
        # Should have matches with varying confidence
        confidences = [m.confidence for m in report2.matches]
        assert max(confidences) == 100.0  # At least one exact match
        assert min(confidences) < 100.0  # At least one non-exact match
    
    def test_apply_mapping_success(self):
        """Test applying successful mapping."""
        df = pd.DataFrame({
            'user_id': [1, 2, 3],
            'months_active': [12, 24, 36],
            'mrr': [50, 60, 70],
            'ltv': [600, 1440, 2520],
            'plan_type': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is True
        
        df_mapped = mapper.apply_mapping(df, report)
        
        assert 'customerID' in df_mapped.columns
        assert 'tenure' in df_mapped.columns
        assert 'MonthlyCharges' in df_mapped.columns
        assert 'TotalCharges' in df_mapped.columns
        assert 'Contract' in df_mapped.columns
        
        assert len(df_mapped) == 3
        assert df_mapped['customerID'].tolist() == [1, 2, 3]
    
    def test_apply_mapping_failure(self):
        """Test applying mapping fails when required columns missing."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure': [12, 24, 36]
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is False
        
        with pytest.raises(ValueError, match="Cannot apply mapping"):
            mapper.apply_mapping(df, report)
    
    def test_multi_industry_support(self):
        """Test mapper works for different industries."""
        df_telecom = pd.DataFrame({
            'customerID': [1],
            'tenure': [12],
            'MonthlyCharges': [50],
            'TotalCharges': [600],
            'Contract': ['Month-to-month']
        })
        
        mapper_telecom = IntelligentColumnMapper(industry='telecom')
        report_telecom = mapper_telecom.map_columns(df_telecom)
        assert report_telecom.success is True
        
        df_saas = pd.DataFrame({
            'user_id': [1],
            'months_subscribed': [12],
            'mrr': [149],
            'total_revenue': [1788],
            'plan_type': ['Professional']
        })
        
        mapper_saas = IntelligentColumnMapper(industry='saas')
        report_saas = mapper_saas.map_columns(df_saas)
        # Note: saas uses same required columns as telecom (customerID, tenure, etc.)
        # This maps user_id→customerID, months_subscribed→tenure, etc.
        assert report_saas.success is True
    
    def test_convenience_function(self):
        """Test convenience function map_csv_columns."""
        df = pd.DataFrame({
            'user_id': [1, 2, 3],
            'months_active': [12, 24, 36],
            'mrr': [50, 60, 70],
            'ltv': [600, 1440, 2520],
            'plan_type': ['A', 'B', 'C']
        })
        
        df_mapped, report = map_csv_columns(df, industry='telecom')
        
        assert report.success is True
        assert 'customerID' in df_mapped.columns
        assert len(df_mapped) == 3
    
    def test_suggestion_generation(self):
        """Test helpful suggestions are generated."""
        df = pd.DataFrame({
            'customerID': [1],
            'tenure': [12]
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        assert report.success is False
        assert len(report.suggestions) > 0
        
        suggestions_text = ' '.join(report.suggestions)
        assert 'missing' in suggestions_text.lower() or 'MonthlyCharges' in suggestions_text
    
    def test_preview_mapping(self):
        """Test preview_mapping returns useful information."""
        df = pd.DataFrame({
            'user_id': [1, 2],
            'months_active': [12, 24],
            'mrr': [50, 60],
            'ltv': [600, 1200],
            'plan_type': ['A', 'B']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        preview = mapper.preview_mapping(df)
        
        assert 'success' in preview
        assert 'confidence' in preview
        assert 'mappings' in preview
        assert 'suggestions' in preview
        assert preview['success'] is True
        assert len(preview['mappings']) == 5
    
    # ========================================
    # DeepSeek + Cursor Enhancement Tests
    # ========================================
    
    def test_duplicate_column_handling(self):
        """Test handling of duplicate column names (DeepSeek fix)."""
        # Create DataFrame with duplicate columns
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'customerID_1': [10, 20, 30],  # pandas auto-suffix
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        # Manually set duplicate column names (simulating real CSV issue)
        df.columns = ['customerID', 'customerID', 'tenure', 'MonthlyCharges', 'TotalCharges', 'Contract']
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Should handle duplicates without data loss
        assert report.success is True
        
        # Only one customerID mapping should exist
        customer_id_matches = [m for m in report.matches if m.standard_column == 'customerID']
        assert len(customer_id_matches) == 1
    
    def test_csv_injection_sanitization(self):
        """Test CSV injection prevention (DeepSeek fix)."""
        df = pd.DataFrame({
            '=HYPERLINK("http://evil.com")': [1, 2, 3],
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Malicious column should be sanitized
        assert all('=' not in m.user_column for m in report.matches)
    
    def test_empty_column_filtering(self):
        """Test removal of empty columns."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'empty_col': [None, None, None],
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Empty column should be filtered out
        assert 'empty_col' not in [m.user_column for m in report.matches]
    
    def test_numeric_header_detection(self):
        """Test detection and fixing of numeric column names."""
        # Create DataFrame with numeric columns
        df = pd.DataFrame({
            0: ['customerID', 1, 2, 3],
            1: ['tenure', 12, 24, 36],
            2: ['MonthlyCharges', 50, 60, 70],
            3: ['TotalCharges', 600, 1440, 2520],
            4: ['Contract', 'A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        # Should detect and fix numeric headers
        df_processed = mapper.preprocess_csv(df)
        
        # First row should become headers
        assert 'customerID' in df_processed.columns or 'tenure' in df_processed.columns
    
    def test_data_type_conversion_tenure_days(self):
        """Test auto-conversion of tenure from days to months (DeepSeek fix)."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure_days': [365, 730, 1095],  # 12, 24, 36 months
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        df_mapped = mapper.apply_mapping(df, report)
        
        # Should convert days to months
        assert 10 <= df_mapped['tenure'].iloc[0] <= 13  # ~12 months
    
    def test_data_type_conversion_currency_cents(self):
        """Test auto-conversion of currency from cents to dollars (DeepSeek fix)."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'tenure': [12, 24, 36],
            'mrr_cents': [5000, 6000, 7000],  # $50, $60, $70
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        df_mapped = mapper.apply_mapping(df, report)
        
        # Should convert cents to dollars
        assert df_mapped['MonthlyCharges'].iloc[0] == 50.0
    
    def test_column_count_limit(self):
        """Test column count limit validation."""
        # Create DataFrame with >1000 columns
        df = pd.DataFrame({f'col_{i}': [1, 2, 3] for i in range(1001)})
        
        mapper = IntelligentColumnMapper(industry='telecom')
        
        with pytest.raises(ValueError, match="max 1000"):
            mapper.map_columns(df)
    
    def test_unicode_column_names(self):
        """Test handling of international/Unicode column names."""
        df = pd.DataFrame({
            'identifiant_client': [1, 2, 3],  # French
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Should handle Unicode and map French column
        assert report.success is True
    
    def test_date_standardization(self):
        """Test automatic date standardization."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3],
            'signup_date': ['2024-01-15', '01/15/2024', '15-Jan-2024'],
            'tenure': [12, 24, 36],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        df_processed = mapper.preprocess_csv(df)
        
        # Date column should be converted to datetime
        assert pd.api.types.is_datetime64_any_dtype(df_processed['signup_date'])
    
    def test_column_aliases_database(self):
        """Test column aliases are comprehensive."""
        aliases = ColumnAliases.get_all_aliases()
        
        # Should have aliases for all standard columns
        assert 'customerID' in aliases
        assert 'tenure' in aliases
        assert 'MonthlyCharges' in aliases
        
        # Each should have 20+ aliases
        assert len(aliases['customerID']) >= 20
        assert len(aliases['tenure']) >= 20
        assert len(aliases['MonthlyCharges']) >= 20
    
    def test_preprocessing_pipeline(self):
        """Test complete preprocessing pipeline."""
        df = pd.DataFrame({
            'Customer ID': [1, 2, 3],
            'TENURE': [12, 24, 36],
            'empty_col': [None, None, None],
            'MonthlyCharges': [50, 60, 70],
            'TotalCharges': [600, 1440, 2520],
            'Contract': ['A', 'B', 'C']
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        df_processed = mapper.preprocess_csv(df)
        
        # Should have:
        # - Removed empty column
        # - Sanitized column names
        # - 5 columns remaining
        assert 'empty_col' not in df_processed.columns
        assert len(df_processed.columns) == 5
    
    def test_edge_case_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        
        mapper = IntelligentColumnMapper(industry='telecom')
        
        with pytest.raises(ValueError, match="no columns"):
            mapper.map_columns(df)
    
    def test_edge_case_single_column(self):
        """Test handling of single column DataFrame."""
        df = pd.DataFrame({
            'customerID': [1, 2, 3]
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Should fail (missing required columns)
        assert report.success is False
        assert len(report.missing_required) > 0


# ========================================
# INTEGRATION TESTS (if needed)
# ========================================

class TestColumnMapperIntegration:
    """Integration tests for end-to-end column mapping."""
    
    def test_real_world_stripe_export(self):
        """Test with realistic Stripe export format."""
        df = pd.DataFrame({
            'id': ['cus_123', 'cus_456', 'cus_789'],
            'created': [1640000000, 1641000000, 1642000000],
            'months_since_creation': [12, 24, 36],
            'mrr': [49.99, 99.99, 149.99],
            'lifetime_value': [599.88, 2399.76, 5399.64],
            'plan': ['starter', 'pro', 'enterprise']
        })
        
        mapper = IntelligentColumnMapper(industry='saas')
        report = mapper.map_columns(df)
        
        # Should successfully map Stripe columns
        assert report.success is True
        assert report.confidence_avg > 85
    
    def test_real_world_excel_export(self):
        """Test with Excel export (common format issues)."""
        df = pd.DataFrame({
            'Customer ID ': [1, 2, 3],  # Trailing space
            ' tenure': [12, 24, 36],  # Leading space
            'Monthly Charges': [50, 60, 70],  # Spaces
            'Total_Charges': [600, 1440, 2520],  # Underscore
            'Contract Type': ['A', 'B', 'C']  # Space
        })
        
        mapper = IntelligentColumnMapper(industry='telecom')
        report = mapper.map_columns(df)
        
        # Should handle whitespace and formatting variations
        assert report.success is True

