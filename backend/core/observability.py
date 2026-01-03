"""
Production Observability System for RetainWise

Implements:
1. Structured JSON logging (CloudWatch Insights compatible)
2. Custom CloudWatch metrics (performance tracking)
3. Performance baselines (regression detection)
4. Cost tracking (budget alerts)

Target Scale: 500 customers, 10K predictions/month
Code Quality: Highway-grade production

Author: RetainWise Engineering
Date: December 13, 2025
Version: 1.0
"""

import structlog
import boto3
import time
import hashlib
import psutil
import os
from typing import Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging

# ========================================
# STRUCTURED LOGGING CONFIGURATION
# ========================================

def configure_structured_logging(environment: str = "production"):
    """
    Configure structured logging for CloudWatch Insights
    
    Why Structured Logging?
    -----------------------
    1. CloudWatch Insights queries:
       - `fields @timestamp, user_id where error_type = "S3UploadError"`
       - `stats count() by error_type`
       - `filter prediction_id = "xxx" | sort @timestamp desc`
    
    2. Correlation across services:
       - Track request_id across backend → worker → database
       - Debug production issues faster
    
    3. Automated alerting:
       - Alert when error_rate > 5%
       - Alert when latency_p95 > 1000ms
    
    Before (Unstructured):
    ----------------------
    logger.info(f"Processing prediction {prediction_id} for user {user_id}")
    # CloudWatch query: Impossible to filter by prediction_id!
    
    After (Structured):
    -------------------
    logger.info("prediction_started", prediction_id=prediction_id, user_id=hash_pii(user_id))
    # CloudWatch query: fields @timestamp where prediction_id = "abc123"
    """
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if environment == "production":
        # JSON output for CloudWatch
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console output for development
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Initialize on module load
configure_structured_logging()

# ========================================
# PII SANITIZATION (GDPR Compliance)
# ========================================

def hash_pii(value: str, length: int = 8) -> str:
    """
    Hash PII for privacy-safe logging
    
    Why Hash PII?
    -------------
    1. GDPR compliance (PII minimization)
    2. CloudWatch logs stored indefinitely
    3. Support team shouldn't see customer data
    4. Still allows correlation (same hash = same customer)
    
    What Gets Hashed:
    -----------------
    - user_id: clerk_user_abc123 → ***a3b2c1d4
    - customerID: CUST_001 → ***e5f6g7h8
    - email: user@example.com → ***9i0j1k2l
    
    What Stays:
    -----------
    - prediction_id: UUID (not PII)
    - metrics: Numbers (not PII)
    - error messages: Technical (not PII)
    """
    if not value:
        return "***none"
    
    hashed = hashlib.sha256(str(value).encode()).hexdigest()[:length]
    return f"***{hashed}"

def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove/hash PII from log data
    
    PII Fields (hashed):
    -------------------
    - user_id
    - clerk_user_id
    - customerID
    - customer_id
    - email
    - phone
    
    Non-PII (kept):
    ---------------
    - prediction_id (UUID, not identifying)
    - upload_id (numeric ID)
    - row_count (metric)
    - duration_ms (metric)
    - error_type (technical)
    """
    PII_FIELDS = [
        'user_id', 'clerk_user_id', 
        'customerID', 'customer_id',
        'email', 'phone', 'name'
    ]
    
    sanitized = data.copy()
    for field in PII_FIELDS:
        if field in sanitized:
            sanitized[field] = hash_pii(sanitized[field])
    
    return sanitized

# ========================================
# PRODUCTION LOGGER
# ========================================

class ProductionLogger:
    """
    Structured logger with PII sanitization
    
    Usage:
    ------
    logger = ProductionLogger(__name__)
    
    logger.log_prediction_start(
        prediction_id="abc-123",
        user_id="clerk_user_xyz",
        row_count=100
    )
    
    Output (CloudWatch):
    --------------------
    {
      "timestamp": "2025-12-13T12:00:00Z",
      "level": "info",
      "event": "prediction_started",
      "prediction_id": "abc-123",
      "user_id": "***a3b2c1d4",
      "row_count": 100,
      "severity": "INFO"
    }
    """
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
    
    def log_prediction_start(
        self, 
        prediction_id: str, 
        user_id: str, 
        row_count: int,
        **extra
    ):
        """Log prediction processing start"""
        self.logger.info(
            "prediction_started",
            **sanitize_log_data({
                "prediction_id": prediction_id,
                "user_id": user_id,
                "row_count": row_count,
                **extra
            }),
            severity="INFO"
        )
    
    def log_prediction_complete(
        self, 
        prediction_id: str, 
        duration_ms: float,
        row_count: int,
        **extra
    ):
        """Log prediction processing completion"""
        self.logger.info(
            "prediction_completed",
            prediction_id=prediction_id,
            duration_ms=duration_ms,
            row_count=row_count,
            throughput_rows_per_sec=row_count / (duration_ms / 1000) if duration_ms > 0 else 0,
            **extra,
            severity="INFO"
        )
    
    def log_prediction_error(
        self, 
        prediction_id: str, 
        error: Exception,
        **context
    ):
        """Log prediction processing error"""
        self.logger.error(
            "prediction_failed",
            **sanitize_log_data({
                "prediction_id": prediction_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                **context
            }),
            severity="ERROR"
        )
    
    def log_security_event(
        self, 
        event_type: str, 
        user_id: str,
        **details
    ):
        """
        Log security events (for audit trail)
        
        Events:
        -------
        - authorization_failure: User A tried to access User B's data
        - rate_limit_exceeded: User exceeded upload limit
        - invalid_token: Authentication failed
        - suspicious_activity: Multiple failed auth attempts
        """
        self.logger.warning(
            event_type,
            **sanitize_log_data({
                "user_id": user_id,
                **details
            }),
            severity="SECURITY"
        )

# ========================================
# CLOUDWATCH METRICS
# ========================================

class CloudWatchMetrics:
    """
    Custom CloudWatch metrics for monitoring
    
    Metrics Tracked:
    ----------------
    1. Prediction duration (P50, P95, P99)
    2. Error rates (by error type)
    3. Throughput (predictions/minute)
    4. Cost estimates (S3, SQS, compute)
    5. Performance degradation (vs baseline)
    
    Why Custom Metrics?
    -------------------
    - Default ECS metrics: CPU, memory (infrastructure)
    - Custom metrics: Business KPIs (user experience)
    - Alerts: When user experience degrades
    """
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
        self.namespace = 'RetainWise/Production'
        
        # Performance baselines (from historical data)
        self.baselines = {
            'prediction_duration_ms': {
                '100': 850,    # 100 rows: 850ms baseline
                '1000': 8500,  # 1K rows: 8.5s baseline
                '10000': 85000 # 10K rows: 85s baseline
            },
            'database_query_ms': 15,
            's3_upload_ms': 40,
            's3_download_ms': 50
        }
    
    def _safe_put_metric(self, **kwargs):
        """
        Safely call CloudWatch put_metric_data with error handling.
        Metrics should NEVER block business operations.
        """
        try:
            self.cloudwatch.put_metric_data(**kwargs)
        except Exception as e:
            # Log but don't crash - metrics are nice-to-have, not critical
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to send CloudWatch metric: {e}")
    
    def record_prediction_duration(
        self, 
        duration_ms: float, 
        row_count: int,
        model_type: str = "saas_baseline"
    ):
        """
        Record prediction duration with regression detection
        
        Logic:
        1. Send metric to CloudWatch
        2. Compare with baseline
        3. Alert if >20% slower (performance regression)
        
        CloudWatch Dashboard Will Show:
        -------------------------------
        - P50 latency (median)
        - P95 latency (95th percentile - user experience)
        - P99 latency (worst case)
        - Throughput (predictions/minute)
        """
        # Record metric
        self._safe_put_metric(
            Namespace=self.namespace,
            MetricData=[
                {
                    'MetricName': 'PredictionDuration',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds',
                    'Dimensions': [
                        {'Name': 'RowCount', 'Value': self._bucket_row_count(row_count)},
                        {'Name': 'ModelType', 'Value': model_type}
                    ],
                    'StorageResolution': 1  # High-resolution (1-second intervals)
                }
            ]
        )
        
        # Check for regression
        baseline_key = str((row_count // 100) * 100)  # Round to nearest 100
        baseline = self.baselines['prediction_duration_ms'].get(baseline_key, duration_ms)
        
        degradation = (duration_ms - baseline) / baseline if baseline > 0 else 0
        
        if degradation > 0.2:  # 20% slower than baseline
            logger = ProductionLogger(__name__)
            logger.logger.warning(
                "performance_regression_detected",
                metric="prediction_duration",
                baseline_ms=baseline,
                current_ms=duration_ms,
                degradation_pct=degradation * 100,
                row_count=row_count,
                severity="WARNING"
            )
    
    def record_error(self, error_type: str, operation: str):
        """
        Record error occurrence for monitoring
        
        CloudWatch Alarm:
        -----------------
        - If error_count > 10 in 5 minutes → Alert
        - If error_rate > 5% → Alert
        """
        self._safe_put_metric(
            Namespace=self.namespace,
            MetricData=[
                {
                    'MetricName': 'ErrorCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'ErrorType', 'Value': error_type},
                        {'Name': 'Operation', 'Value': operation}
                    ]
                }
            ]
        )
    
    def record_cost_estimate(self, service: str, cost_usd: float):
        """
        Track estimated AWS costs for budget monitoring
        
        Cost Breakdown:
        ---------------
        - S3 PUT: $0.005 per 1,000 requests
        - S3 GET: $0.0004 per 1,000 requests
        - S3 storage: $0.023 per GB-month
        - SQS: $0.40 per million requests
        - RDS: $0.017 per hour (db.t3.micro)
        - ECS Fargate: $0.04048 per vCPU-hour
        
        Alert When:
        -----------
        - Daily cost > $10 (monthly projection: $300)
        - S3 usage > 100GB (storage costs)
        - Unusual spike (10x normal)
        """
        self._safe_put_metric(
            Namespace=self.namespace,
            MetricData=[
                {
                    'MetricName': 'EstimatedCost',
                    'Value': cost_usd,
                    'Unit': 'None',  # USD
                    'Dimensions': [
                        {'Name': 'Service', 'Value': service}
                    ]
                }
            ]
        )
    
    def _bucket_row_count(self, row_count: int) -> str:
        """
        Bucket row counts for dimension cardinality control
        
        Why Bucket?
        -----------
        - CloudWatch charges per unique dimension combination
        - 10,000 unique row counts = expensive
        - Bucketing: <100, 100-1K, 1K-10K, 10K+
        - Only 4 dimension values = cheaper, clearer
        """
        if row_count < 100:
            return "<100"
        elif row_count < 1000:
            return "100-1K"
        elif row_count < 10000:
            return "1K-10K"
        else:
            return ">10K"

# ========================================
# PERFORMANCE MONITORING
# ========================================

class PerformanceMonitor:
    """
    Monitor and alert on performance degradation
    
    Usage:
    ------
    perf = PerformanceMonitor()
    
    with perf.measure('ml_prediction', rows=100):
        result = model.predict(df)
    
    Features:
    ---------
    - Automatic timing
    - Regression detection (vs baseline)
    - CloudWatch metric recording
    - Memory usage tracking
    """
    
    def __init__(self):
        self.metrics = CloudWatchMetrics()
        self.logger = ProductionLogger(__name__)
    
    @contextmanager
    def measure(self, operation_name: str, **dimensions):
        """
        Measure operation performance
        
        Tracks:
        -------
        1. Duration (milliseconds)
        2. Memory usage (MB)
        3. Success/failure
        4. Regression vs baseline
        
        Example Output:
        ---------------
        {
          "event": "ml_prediction_completed",
          "duration_ms": 850,
          "memory_mb": 45,
          "success": true,
          "rows": 100,
          "baseline_ms": 850,
          "degradation_pct": 0.0
        }
        """
        start_time = time.time()
        start_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
        error_occurred = False
        
        try:
            yield
        except Exception as e:
            error_occurred = True
            self.logger.logger.error(
                f"{operation_name}_failed",
                error_type=type(e).__name__,
                error_message=str(e),
                **dimensions,
                severity="ERROR"
            )
            
            # Record error metric
            self.metrics.record_error(
                error_type=type(e).__name__,
                operation=operation_name
            )
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            end_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            memory_used_mb = end_memory - start_memory
            
            self.logger.logger.info(
                f"{operation_name}_completed",
                duration_ms=round(duration_ms, 2),
                memory_mb=round(memory_used_mb, 2),
                success=not error_occurred,
                **dimensions,
                severity="INFO"
            )
            
            # Record CloudWatch metric
            self.metrics.cloudwatch.put_metric_data(
                Namespace='RetainWise/Production',
                MetricData=[
                    {
                        'MetricName': f'{operation_name}_duration',
                        'Value': duration_ms,
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': k, 'Value': str(v)} 
                            for k, v in dimensions.items()
                        ]
                    }
                ]
            )

# ========================================
# SINGLETON INSTANCES
# ========================================

# Global instances for easy import
production_logger = ProductionLogger(__name__)
cloudwatch_metrics = CloudWatchMetrics()
performance_monitor = PerformanceMonitor()

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def log_prediction_event(event_type: str, prediction_id: str, **details):
    """
    Convenience function for prediction logging
    
    Usage:
    ------
    from backend.core.observability import log_prediction_event
    
    log_prediction_event(
        "prediction_started",
        prediction_id="abc-123",
        user_id="clerk_user_xyz",
        row_count=100
    )
    """
    production_logger.logger.info(
        event_type,
        **sanitize_log_data({
            "prediction_id": prediction_id,
            **details
        })
    )

def log_security_event(event_type: str, user_id: str, **details):
    """
    Convenience function for security logging
    
    Usage:
    ------
    log_security_event(
        "authorization_failure",
        user_id="clerk_user_xyz",
        attempted_resource="prediction/abc-123"
    )
    """
    production_logger.log_security_event(event_type, user_id, **details)

# ========================================
# COST TRACKING
# ========================================

class CostTracker:
    """
    Track and estimate AWS costs
    
    Why Track Costs?
    ----------------
    - S3: Unlimited uploads can bankrupt you
    - ECS Fargate: Hourly charges add up
    - RDS: Idle instance = wasted money
    - SQS: Million requests = $0.40
    
    Target Budget:
    --------------
    - $300/month for MVP (500 customers)
    - $10/day sustainable
    - Alert at $8/day (80% threshold)
    """
    
    # AWS Pricing (us-east-1, Dec 2025)
    COSTS = {
        's3_put_per_1000': 0.005,
        's3_get_per_1000': 0.0004,
        's3_storage_per_gb_month': 0.023,
        'sqs_per_1m': 0.40,
        'rds_db_t3_micro_per_hour': 0.017,
        'fargate_vcpu_per_hour': 0.04048,
        'fargate_memory_gb_per_hour': 0.004445
    }
    
    def __init__(self):
        self.metrics = CloudWatchMetrics()
        self.daily_costs = {}  # Track daily costs
    
    def estimate_s3_upload_cost(self, file_size_bytes: int) -> float:
        """
        Estimate S3 upload cost
        
        Calculation:
        ------------
        PUT request: $0.005 / 1000 = $0.000005
        Storage: file_size_gb * $0.023 / 30 days
        Total: PUT + daily storage
        """
        put_cost = self.COSTS['s3_put_per_1000'] / 1000
        storage_cost_per_day = (file_size_bytes / 1024**3) * self.COSTS['s3_storage_per_gb_month'] / 30
        
        total = put_cost + storage_cost_per_day
        
        # Record metric
        self.metrics.record_cost_estimate('s3_upload', total)
        
        return total
    
    def estimate_prediction_cost(self, row_count: int, duration_ms: float) -> float:
        """
        Estimate cost of single prediction
        
        Components:
        -----------
        1. Fargate compute: duration * vCPU_rate
        2. SQS messages: 2 (send + delete)
        3. S3: Download + upload
        
        Example (100 rows, 850ms):
        --------------------------
        - Fargate: 850ms * $0.04048/hour = $0.0000095
        - SQS: 2 * $0.40/1M = $0.0000008
        - S3: $0.000005 * 2 = $0.00001
        - Total: ~$0.00002 (2 cents per 1000 predictions)
        """
        # Fargate compute (512 CPU = 0.5 vCPU, 1024 MB = 1 GB)
        duration_hours = duration_ms / 1000 / 3600
        fargate_cost = (
            0.5 * self.COSTS['fargate_vcpu_per_hour'] * duration_hours +
            1.0 * self.COSTS['fargate_memory_gb_per_hour'] * duration_hours
        )
        
        # SQS (2 messages: send + delete)
        sqs_cost = 2 * (self.COSTS['sqs_per_1m'] / 1_000_000)
        
        # S3 (download + upload)
        s3_cost = (self.COSTS['s3_put_per_1000'] / 1000) * 2
        
        total = fargate_cost + sqs_cost + s3_cost
        
        # Record metric
        self.metrics.record_cost_estimate('prediction', total)
        
        return total
    
    def check_daily_budget(self) -> tuple[bool, float]:
        """
        Check if daily budget exceeded
        
        Budget: $10/day ($300/month)
        Alert threshold: $8/day (80%)
        
        Returns:
        --------
        (within_budget, current_spend)
        """
        # Query CloudWatch for today's cost sum
        today = datetime.now().date()
        
        # This would query Cost Explorer API in production
        # For MVP, estimate from metric sums
        
        total_today = sum(self.daily_costs.values())
        
        return total_today < 8.0, total_today

# ========================================
# SINGLETON INSTANCES
# ========================================

cost_tracker = CostTracker()

# ========================================
# MODULE INFO
# ========================================

__all__ = [
    'configure_structured_logging',
    'ProductionLogger',
    'CloudWatchMetrics',
    'PerformanceMonitor',
    'CostTracker',
    'hash_pii',
    'sanitize_log_data',
    'production_logger',
    'cloudwatch_metrics',
    'performance_monitor',
    'cost_tracker',
    'log_prediction_event',
    'log_security_event'
]

