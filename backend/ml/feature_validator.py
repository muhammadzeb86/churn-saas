"""
Production-Grade Feature Validator for SaaS Churn Prediction

Design Principles:
1. Simple & Fast: 150 lines of focused validation logic
2. Actionable Feedback: Clear error messages with fix suggestions
3. ML-Ready: Validates data quality for accurate predictions
4. Secure: No PII leakage in error messages
5. Production-Grade: Monitoring metrics, proper error handling

Validation Layers:
- Layer 1: Schema (required fields present)
- Layer 2: Data Types (correct pandas dtypes)
- Layer 3: Value Ranges (min/max constraints)
- Layer 4: Business Rules (cross-field validation)
- Layer 5: ML Readiness (sample size, balance, correlation)

Usage:
    validator = SaaSFeatureValidator(level='standard')
    result = validator.validate(df)
    
    if not result.is_valid:
        for error in result.errors:
            print(f"❌ {error['message']} → Fix: {error['action']}")

Author: RetainWise ML Team
Date: December 8, 2025
Version: 1.0 (Production)
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


# ========================================
# DATA STRUCTURES
# ========================================

class ValidationLevel(str, Enum):
    """
    Validation strictness levels.
    
    MINIMAL: Only check blocking errors (missing required fields, wrong types)
    STANDARD: All SaaS best practices (default, recommended)
    ML_TRAINING: Extra checks for training data (class balance, sample size)
    """
    MINIMAL = "minimal"
    STANDARD = "standard"
    ML_TRAINING = "ml_training"


class IssueType(str, Enum):
    """Issue severity levels."""
    ERROR = "error"      # Blocks prediction
    WARNING = "warning"  # Prediction proceeds but quality affected
    INFO = "info"        # Suggestions for improvement


@dataclass
class ValidationIssue:
    """
    Single validation issue with actionable feedback.
    
    Attributes:
        issue_type: Error, warning, or info
        field: Column name affected
        message: What's wrong (clear, concise)
        action: How to fix it (actionable)
        affected_rows: Number of rows with this issue
        sample_indices: Row numbers with issues (for debugging)
    """
    issue_type: IssueType
    field: str
    message: str
    action: str
    affected_rows: int = 0
    sample_indices: List[int] = field(default_factory=list)


@dataclass
class ValidationResult:
    """
    Complete validation result with actionable feedback.
    
    Attributes:
        is_valid: True if no blocking errors
        errors: List of blocking issues
        warnings: List of quality issues (non-blocking)
        info: List of suggestions
        total_rows: Dataset size
        metrics: Dict of numeric metrics for monitoring (CloudWatch)
    """
    is_valid: bool
    errors: List[ValidationIssue]
    warnings: List[ValidationIssue]
    info: List[ValidationIssue]
    total_rows: int
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def get_summary(self) -> Dict:
        """Get user-friendly summary (no arbitrary scores)."""
        status = "✅ Ready for prediction" if self.is_valid else "❌ Needs fixes"
        
        return {
            'status': status,
            'total_rows': self.total_rows,
            'critical_issues': len(self.errors),
            'data_warnings': len(self.warnings),
            'suggestions': len(self.info),
            'details': {
                'errors': [
                    {
                        'field': e.field,
                        'message': e.message,
                        'fix': e.action,
                        'affected_rows': e.affected_rows
                    }
                    for e in self.errors[:5]  # First 5 errors
                ],
                'warnings': [
                    {
                        'field': w.field,
                        'message': w.message,
                        'suggestion': w.action
                    }
                    for w in self.warnings[:3]  # First 3 warnings
                ]
            }
        }


# ========================================
# SAAS VALIDATION RULES
# ========================================

class SaaSValidationRules:
    """SaaS-specific validation rules based on industry standards."""
    
    REQUIRED_FIELDS = {
        'customerID': {
            'dtype': 'string',
            'unique': True,
            'description': 'Unique customer identifier'
        },
        'tenure': {
            'dtype': 'numeric',
            'min': 0,
            'max': 120,  # 10 years max
            'description': 'Months since customer signup'
        },
        'MonthlyCharges': {
            'dtype': 'numeric',
            'min': 0.01,
            'max': 100000,  # $100K/month ceiling
            'description': 'Monthly recurring revenue per customer'
        },
        'TotalCharges': {
            'dtype': 'numeric',
            'min': 0,
            'max': 10000000,  # $10M lifetime value ceiling
            'allow_null': True,  # New customers may have null
            'description': 'Lifetime revenue from customer'
        },
        'Contract': {
            'dtype': 'categorical',
            'allowed_values': {
                'Month-to-month', 'Monthly', 'Quarterly', 'Annual', 'Yearly', 'Two year', 'Multi-year'
            },
            'description': 'Contract type'
        }
    }
    
    OPTIONAL_FIELDS = {
        'seats_purchased': {
            'dtype': 'numeric',
            'min': 1,
            'max': 100000,
            'description': 'Number of licenses purchased'
        },
        'seats_used': {
            'dtype': 'numeric',
            'min': 0,
            'max': 100000,
            'description': 'Number of licenses actively used'
        },
        'feature_usage_score': {
            'dtype': 'numeric',
            'min': 0,
            'max': 100,
            'description': 'Percentage of features used (0-100%)'
        },
        'last_activity_days_ago': {
            'dtype': 'numeric',
            'min': 0,
            'max': 365,
            'description': 'Days since last login/activity'
        },
        'support_tickets': {
            'dtype': 'numeric',
            'min': 0,
            'max': 1000,
            'description': 'Number of support tickets filed'
        }
    }


# ========================================
# MAIN VALIDATOR
# ========================================

class SaaSFeatureValidator:
    """
    Production-grade feature validator for SaaS churn prediction.
    
    Fast, secure, actionable validation with ML readiness checks.
    """
    
    def __init__(self, level: ValidationLevel = ValidationLevel.STANDARD):
        """
        Initialize validator with specified validation level.
        
        Args:
            level: MINIMAL (errors only), STANDARD (best practices), ML_TRAINING (extra checks)
        """
        self.level = level
        self.required_fields = SaaSValidationRules.REQUIRED_FIELDS
        self.optional_fields = SaaSValidationRules.OPTIONAL_FIELDS
        
        logger.info(f"SaaSFeatureValidator initialized with level={level.value}")
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """
        Validate DataFrame with comprehensive checks.
        
        Args:
            df: DataFrame to validate (after column mapping)
            
        Returns:
            ValidationResult with errors, warnings, and metrics
        """
        logger.info(f"Validating {len(df)} rows at level={self.level.value}")
        
        errors = []
        warnings = []
        info = []
        
        # Layer 1: Schema Validation
        errors.extend(self._validate_schema(df))
        
        # Layer 2-3: Field Validation (types + ranges)
        for field_name, rules in self.required_fields.items():
            if field_name in df.columns:
                issues = self._validate_field(df, field_name, rules, required=True)
                self._categorize_issues(issues, errors, warnings, info)
        
        for field_name, rules in self.optional_fields.items():
            if field_name in df.columns:
                issues = self._validate_field(df, field_name, rules, required=False)
                self._categorize_issues(issues, errors, warnings, info)
        
        # Layer 4: Business Rules (cross-field validation)
        if self.level in [ValidationLevel.STANDARD, ValidationLevel.ML_TRAINING]:
            business_issues = self._validate_business_rules(df)
            self._categorize_issues(business_issues, errors, warnings, info)
        
        # Layer 5: ML Readiness Checks
        if self.level == ValidationLevel.ML_TRAINING:
            ml_issues = self._validate_ml_readiness(df)
            self._categorize_issues(ml_issues, errors, warnings, info)
        
        # Calculate metrics for monitoring (CloudWatch)
        metrics = self._calculate_metrics(df, errors, warnings)
        
        result = ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            info=info,
            total_rows=len(df),
            metrics=metrics
        )
        
        logger.info(
            f"Validation complete: valid={result.is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}, "
            f"quality_score={metrics.get('quality_score', 0):.1f}"
        )
        
        return result
    
    def _validate_schema(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check required fields are present."""
        issues = []
        
        missing_fields = [
            field for field in self.required_fields.keys()
            if field not in df.columns
        ]
        
        if missing_fields:
            issues.append(ValidationIssue(
                issue_type=IssueType.ERROR,
                field='schema',
                message=f"Missing {len(missing_fields)} required field(s): {', '.join(missing_fields)}",
                action=f"Add these columns to your CSV: {', '.join(missing_fields)}",
                affected_rows=len(df)
            ))
        
        return issues
    
    def _validate_field(
        self,
        df: pd.DataFrame,
        field_name: str,
        rules: Dict,
        required: bool
    ) -> List[ValidationIssue]:
        """
        Validate a single field against its rules.
        
        Checks:
        - Data type (pandas dtype)
        - Value ranges (min/max)
        - Allowed values (categorical)
        - Null values
        """
        issues = []
        series = df[field_name]
        
        # Check data type (FIXED: Check actual dtype, not just content)
        dtype_issue = self._check_dtype(series, rules['dtype'])
        if dtype_issue:
            issues.append(dtype_issue)
            return issues  # Can't check ranges if wrong type
        
        # Check null values
        if not rules.get('allow_null', False):
            null_count = series.isnull().sum()
            if null_count > 0:
                issues.append(ValidationIssue(
                    issue_type=IssueType.ERROR if required else IssueType.WARNING,
                    field=field_name,
                    message=f"{null_count} null values ({null_count/len(df)*100:.1f}%)",
                    action=f"Fill missing values for '{field_name}'",
                    affected_rows=null_count,
                    sample_indices=df[series.isnull()].index[:5].tolist()
                ))
        
        # Check value ranges (numeric only)
        if rules['dtype'] == 'numeric':
            # Convert to numeric, coercing errors to NaN
            numeric = pd.to_numeric(series, errors='coerce')
            
            # Only check ranges on non-null numeric values
            if 'min' in rules:
                # Compare only valid (non-NaN) numeric values
                valid_mask = numeric.notna()
                below_min = valid_mask & (numeric < rules['min'])
                if below_min.any():
                    sample_values = series[below_min].head(3).tolist()
                    issues.append(ValidationIssue(
                        issue_type=IssueType.ERROR if required else IssueType.WARNING,
                        field=field_name,
                        message=f"{below_min.sum()} value(s) below minimum {rules['min']}. Examples: {sample_values}",
                        action=f"Values should be ≥ {rules['min']}",
                        affected_rows=below_min.sum(),
                        sample_indices=df[below_min].index[:5].tolist()
                    ))
            
            if 'max' in rules:
                # Compare only valid (non-NaN) numeric values
                valid_mask = numeric.notna()
                above_max = valid_mask & (numeric > rules['max'])
                if above_max.any():
                    sample_values = series[above_max].head(3).tolist()
                    issues.append(ValidationIssue(
                        issue_type=IssueType.ERROR if required else IssueType.WARNING,
                        field=field_name,
                        message=f"{above_max.sum()} value(s) above maximum {rules['max']}. Examples: {sample_values}",
                        action=f"Values should be ≤ {rules['max']}",
                        affected_rows=above_max.sum(),
                        sample_indices=df[above_max].index[:5].tolist()
                    ))
        
        # Check categorical values
        if rules['dtype'] == 'categorical' and 'allowed_values' in rules:
            invalid = ~series.isin(rules['allowed_values'])
            if invalid.any():
                unique_invalid = series[invalid].unique()[:3]
                issues.append(ValidationIssue(
                    issue_type=IssueType.ERROR,
                    field=field_name,
                    message=f"{invalid.sum()} invalid value(s). Found: {list(unique_invalid)}",
                    action=f"Allowed: {', '.join(sorted(rules['allowed_values']))}",
                    affected_rows=invalid.sum(),
                    sample_indices=df[invalid].index[:5].tolist()
                ))
        
        # Check uniqueness
        if rules.get('unique', False):
            duplicates = series.duplicated()
            if duplicates.any():
                # PII-SAFE: Don't show actual customer IDs, show row indices
                dupe_indices = df[duplicates].index[:3].tolist()
                issues.append(ValidationIssue(
                    issue_type=IssueType.ERROR,
                    field=field_name,
                    message=f"{duplicates.sum()} duplicate value(s) found",
                    action=f"Each {field_name} should be unique. Check rows: {dupe_indices}",
                    affected_rows=duplicates.sum(),
                    sample_indices=dupe_indices
                ))
        
        return issues
    
    def _check_dtype(self, series: pd.Series, expected_dtype: str) -> Optional[ValidationIssue]:
        """
        Check if series has correct data type.
        
        FIXED: Checks actual pandas dtype, not just content convertibility.
        """
        if expected_dtype == 'numeric':
            if not pd.api.types.is_numeric_dtype(series):
                # Try to convert to see if it's convertible
                try:
                    pd.to_numeric(series.dropna(), errors='raise')
                    # Convertible but wrong dtype
                    return ValidationIssue(
                        issue_type=IssueType.WARNING,
                        field=series.name,
                        message=f"Column '{series.name}' is {series.dtype}, should be numeric",
                        action="Data type will be converted automatically",
                        affected_rows=0
                    )
                except:
                    # Not convertible
                    non_numeric = pd.to_numeric(series, errors='coerce').isna() & series.notna()
                    sample = series[non_numeric].head(3).tolist()
                    return ValidationIssue(
                        issue_type=IssueType.ERROR,
                        field=series.name,
                        message=f"Column '{series.name}' contains non-numeric values. Examples: {sample}",
                        action="Remove text, commas, symbols. Use only numbers.",
                        affected_rows=non_numeric.sum()
                    )
        
        elif expected_dtype == 'string':
            if series.dtype != 'object':
                return ValidationIssue(
                    issue_type=IssueType.WARNING,
                    field=series.name,
                    message=f"Column '{series.name}' is {series.dtype}, expected text",
                    action="Expected text values like customer IDs or names",
                    affected_rows=0
                )
        
        return None
    
    def _validate_business_rules(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Validate cross-field business rules.
        
        Rules:
        - seats_used <= seats_purchased
        - TotalCharges >= MonthlyCharges (for tenure >= 1)
        - New customers (tenure=0) should have low/null TotalCharges
        
        NOTE: All numeric comparisons use pd.to_numeric with errors='coerce'
        to safely handle non-numeric or null values.
        """
        issues = []
        
        # Rule 1: Seats validation
        if {'seats_purchased', 'seats_used'}.issubset(df.columns):
            # Convert to numeric to handle any non-numeric values safely
            seats_purchased = pd.to_numeric(df['seats_purchased'], errors='coerce')
            seats_used = pd.to_numeric(df['seats_used'], errors='coerce')
            
            # Only compare where both values are valid (not NaN)
            valid_mask = seats_purchased.notna() & seats_used.notna()
            invalid = valid_mask & (seats_used > seats_purchased)
            
            if invalid.any():
                # PII-SAFE: Show row indices, not customer IDs
                sample_indices = df[invalid].index[:3].tolist()
                issues.append(ValidationIssue(
                    issue_type=IssueType.ERROR,
                    field='seats_used',
                    message=f"{invalid.sum()} customer(s) using more seats than purchased",
                    action=f"Check data integrity for rows: {sample_indices}",
                    affected_rows=invalid.sum(),
                    sample_indices=sample_indices
                ))
        
        # Rule 2: Total vs Monthly charges
        if {'tenure', 'TotalCharges', 'MonthlyCharges'}.issubset(df.columns):
            # Convert all to numeric to handle any non-numeric values safely
            tenure = pd.to_numeric(df['tenure'], errors='coerce')
            total_charges = pd.to_numeric(df['TotalCharges'], errors='coerce')
            monthly_charges = pd.to_numeric(df['MonthlyCharges'], errors='coerce')
            
            # Only compare where all values are valid (not NaN)
            valid_mask = (
                tenure.notna() &
                total_charges.notna() &
                monthly_charges.notna()
            )
            
            # Check existing customers (tenure >= 1) with TotalCharges < MonthlyCharges
            mask = valid_mask & (tenure >= 1) & (total_charges < monthly_charges)
            
            if mask.any():
                sample_indices = df[mask].index[:3].tolist()
                issues.append(ValidationIssue(
                    issue_type=IssueType.WARNING,
                    field='TotalCharges',
                    message=f"{mask.sum()} customer(s) have TotalCharges < MonthlyCharges",
                    action=f"May indicate refunds or data errors. Check rows: {sample_indices}",
                    affected_rows=mask.sum(),
                    sample_indices=sample_indices
                ))
        
        return issues
    
    def _validate_ml_readiness(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Validate data is ready for ML predictions/training.
        
        Checks:
        - Sample size (need enough data)
        - Class balance (for training data)
        - Feature correlation (multicollinearity)
        """
        issues = []
        
        # Check 1: Sample size
        if len(df) < 50:
            issues.append(ValidationIssue(
                issue_type=IssueType.WARNING,
                field='dataset_size',
                message=f"Only {len(df)} rows - predictions may be unreliable",
                action="Upload 50+ customers for more reliable predictions",
                affected_rows=len(df)
            ))
        
        # Check 2: Class balance (if Churn column exists - training data)
        if 'Churn' in df.columns:
            churn_rate = df['Churn'].mean()
            if churn_rate < 0.02:
                issues.append(ValidationIssue(
                    issue_type=IssueType.WARNING,
                    field='Churn',
                    message=f"Very low churn rate ({churn_rate:.1%})",
                    action="Consider oversampling techniques or collect more churned customers",
                    affected_rows=0
                ))
            elif churn_rate > 0.5:
                issues.append(ValidationIssue(
                    issue_type=IssueType.WARNING,
                    field='Churn',
                    message=f"Very high churn rate ({churn_rate:.1%})",
                    action="Unusual for SaaS (typical: 2-20%). Verify data accuracy.",
                    affected_rows=0
                ))
        
        # Check 3: Multicollinearity (high correlation between features)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) >= 2:
            try:
                corr_matrix = df[numeric_cols].corr().abs()
                # Find pairs with correlation > 0.95
                high_corr_pairs = []
                for i in range(len(numeric_cols)):
                    for j in range(i+1, len(numeric_cols)):
                        if corr_matrix.iloc[i, j] > 0.95:
                            high_corr_pairs.append((numeric_cols[i], numeric_cols[j], corr_matrix.iloc[i, j]))
                
                if high_corr_pairs:
                    col1, col2, corr_val = high_corr_pairs[0]
                    issues.append(ValidationIssue(
                        issue_type=IssueType.INFO,
                        field=f"{col1}, {col2}",
                        message=f"High correlation ({corr_val:.2f}) between {col1} and {col2}",
                        action="Highly correlated features may not improve predictions",
                        affected_rows=0
                    ))
            except Exception as e:
                logger.warning(f"Could not calculate correlation matrix: {e}")
        
        return issues
    
    def _categorize_issues(
        self,
        issues: List[ValidationIssue],
        errors: List,
        warnings: List,
        info: List
    ) -> None:
        """Sort issues into errors, warnings, and info lists."""
        for issue in issues:
            if issue.issue_type == IssueType.ERROR:
                errors.append(issue)
            elif issue.issue_type == IssueType.WARNING:
                warnings.append(issue)
            else:
                info.append(issue)
    
    def _calculate_metrics(
        self,
        df: pd.DataFrame,
        errors: List[ValidationIssue],
        warnings: List[ValidationIssue]
    ) -> Dict[str, float]:
        """
        Calculate numeric metrics for monitoring (CloudWatch).
        
        NOT shown to users - used for ops monitoring and alarms.
        """
        # Quality score: Based on % of valid rows
        total_affected = sum(e.affected_rows for e in errors + warnings)
        valid_rows = max(0, len(df) - total_affected)
        quality_score = (valid_rows / len(df) * 100) if len(df) > 0 else 0
        
        # Completeness: % of optional fields present
        optional_present = sum(1 for field in self.optional_fields if field in df.columns)
        completeness = (optional_present / len(self.optional_fields) * 100)
        
        return {
            'quality_score': quality_score,
            'completeness_score': completeness,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'total_rows': len(df),
            'valid_rows': valid_rows
        }


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def validate_saas_data(
    df: pd.DataFrame,
    level: ValidationLevel = ValidationLevel.STANDARD
) -> ValidationResult:
    """
    Quick validation function for SaaS data.
    
    Args:
        df: DataFrame to validate
        level: Validation strictness level
        
    Returns:
        ValidationResult with errors, warnings, and metrics
    """
    validator = SaaSFeatureValidator(level=level)
    return validator.validate(df)

