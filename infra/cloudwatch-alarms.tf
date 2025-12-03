# CloudWatch Alarms for RetainWise ML Pipeline
#
# DESIGN PHILOSOPHY (Revised after analysis):
# =============================================
# 1. Use ERROR RATES (%), not absolute counts
# 2. Two severity levels: CRITICAL (page ops) and WARNING (investigate)
# 3. Tuned thresholds based on percentiles (avoid false positives)
# 4. Actionable alerts with resolution steps
# 5. ML-specific monitoring (model performance, drift)
#
# CRITICAL FIXES FROM DEEPSEEK ANALYSIS:
# =======================================
# - Changed absolute counts to percentage rates
# - Added metric math for error rate calculations
# - Added ML-specific alarms (model confidence, loading failures)
# - Added SQS message age alarm
#
# Author: AI Assistant (Revised - Hybrid Approach)
# Date: December 3, 2025

# ===========================
# 1. SQS QUEUE DEPTH ALARM (UNCHANGED - Already Correct)
# ===========================

resource "aws_cloudwatch_metric_alarm" "sqs_queue_depth_high" {
  alarm_name          = "retainwise-sqs-queue-depth-high"
  alarm_description   = <<EOF
CRITICAL: SQS queue depth > 10 for 5 minutes.

IMPACT: Predictions delayed, customer experience degraded.

RESOLUTION:
1. Check worker service health: aws ecs describe-services --cluster retainwise-prod --services retainwise-worker
2. Check worker logs: aws logs tail /ecs/retainwise-worker --follow
3. Scale worker count if processing backlog: aws ecs update-service --cluster retainwise-prod --service retainwise-worker --desired-count 3
4. Check for DLQ messages (failed predictions): aws sqs get-queue-attributes --queue-url <DLQ_URL>
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300  # 5 minutes
  statistic           = "Average"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    QueueName = aws_sqs_queue.predictions_queue.name
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-sqs-queue-depth"
    Severity    = "critical"
    Environment = "production"
  }
}

# ===========================
# 2. SQS MESSAGE AGE ALARM (NEW - DeepSeek suggestion)
# ===========================

resource "aws_cloudwatch_metric_alarm" "sqs_message_age_high" {
  alarm_name          = "retainwise-sqs-message-age-high"
  alarm_description   = <<EOF
WARNING: Oldest SQS message > 30 minutes old.

IMPACT: Customer is waiting too long for predictions.

RESOLUTION:
1. Check if worker is running: aws ecs list-tasks --cluster retainwise-prod --service-name retainwise-worker
2. If no tasks, worker may have crashed - check ECS events
3. If tasks running, check worker CPU/memory - may need to scale
4. Check CloudWatch logs for stuck processing
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 1800  # 30 minutes in seconds
  
  metric_name = "ApproximateAgeOfOldestMessage"
  namespace   = "AWS/SQS"
  period      = 300  # 5 minutes
  statistic   = "Maximum"
  
  dimensions = {
    QueueName = aws_sqs_queue.predictions_queue.name
  }
  
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions         = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-sqs-message-age"
    Severity    = "warning"
    Environment = "production"
  }
}

# ===========================
# 3. DLQ MESSAGES ALARM (UNCHANGED - Already Correct)
# ===========================

resource "aws_cloudwatch_metric_alarm" "dlq_messages_present" {
  alarm_name          = "retainwise-dlq-messages-present"
  alarm_description   = <<EOF
CRITICAL: Messages in Dead Letter Queue (DLQ).

IMPACT: Predictions failed after 3 retries, customers not receiving results.

RESOLUTION:
1. Check DLQ messages: aws sqs receive-message --queue-url <DLQ_URL>
2. Identify failure pattern in worker logs
3. Fix root cause (CSV format, model loading, database issue)
4. Replay DLQ messages after fix: python scripts/replay_dlq_messages.py
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60  # 1 minute (check frequently)
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    QueueName = aws_sqs_queue.predictions_dlq.name
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-dlq-messages"
    Severity    = "critical"
    Environment = "production"
  }
}

# ===========================
# 4. WORKER ERROR RATE (✅ FIXED - Now uses percentage)
# ===========================

resource "aws_cloudwatch_metric_alarm" "worker_error_rate_high" {
  alarm_name          = "retainwise-worker-error-rate-high"
  alarm_description   = <<EOF
WARNING: Worker error rate > 5% for 15 minutes.

CALCULATION: (errors / (errors + successes)) * 100

IMPACT: Some predictions failing, customer frustration increasing.

RESOLUTION:
1. Check worker logs: aws logs tail /ecs/retainwise-worker --follow --filter-pattern "ERROR"
2. Identify common failure (CSV parse, model load, S3 access)
3. If CSV format issue: Update column mapper or add validation
4. If model issue: Verify S3 model file integrity
5. If S3 access issue: Check IAM permissions
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3  # 3 periods × 5 min = 15 min total
  threshold           = 5  # 5% error rate
  treat_missing_data  = "notBreaching"
  
  # ✅ FIXED: Use metric math for percentage
  metric_query {
    id          = "error_rate"
    expression  = "(errors / (errors + successes)) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }
  
  metric_query {
    id = "errors"
    metric {
      metric_name = "WorkerUnexpectedError"
      namespace   = "RetainWise/Worker"
      period      = 300  # 5 minutes
      stat        = "Sum"
    }
  }
  
  metric_query {
    id = "successes"
    metric {
      metric_name = "WorkerSuccess"
      namespace   = "RetainWise/Worker"
      period      = 300
      stat        = "Sum"
    }
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-worker-error-rate"
    Severity    = "warning"
    Environment = "production"
  }
}

# ===========================
# 5. SLOW PREDICTION PROCESSING (p99, not p95)
# ===========================

resource "aws_cloudwatch_metric_alarm" "prediction_processing_slow" {
  alarm_name          = "retainwise-prediction-processing-slow"
  alarm_description   = <<EOF
WARNING: Worker end-to-end processing time > 5 minutes (p99).

IMPACT: Slow predictions, customers waiting longer than expected.

RESOLUTION:
1. Check worker CPU/memory usage: CloudWatch dashboard → ECS metrics
2. If CPU high: Scale worker instance size (increase Fargate CPU/memory)
3. If I/O slow: Check S3 download time metric, may need VPC endpoint
4. If ML slow: Profile model prediction time, consider model optimization
5. Check for large CSV files: Review CSVRowCount metric
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 300  # 5 minutes (300 seconds)
  treat_missing_data  = "notBreaching"
  
  metric_name        = "WorkerEndToEndDuration"
  namespace          = "RetainWise/Worker"
  period             = 600  # 10 minutes
  extended_statistic = "p99"  # 99th percentile (catch real outliers)
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-prediction-slow"
    Severity    = "warning"
    Environment = "production"
  }
}

# ===========================
# 6. S3 UPLOAD FAILURE RATE (✅ FIXED - Now uses percentage)
# ===========================

resource "aws_cloudwatch_metric_alarm" "s3_upload_failure_rate" {
  alarm_name          = "retainwise-s3-upload-failures"
  alarm_description   = <<EOF
CRITICAL: S3 upload failure rate > 10% for 10 minutes.

CALCULATION: (failures / (successes + failures)) * 100

IMPACT: Users cannot upload CSVs, core functionality broken.

RESOLUTION:
1. Check S3 bucket status: aws s3api head-bucket --bucket retainwise-uploads
2. Verify IAM permissions: Review backend task role S3 policy
3. Check S3 bucket policy: Ensure backend has PutObject permission
4. Check AWS Service Health Dashboard for S3 outages
5. Review backend logs: aws logs tail /ecs/retainwise-backend --follow --filter-pattern "S3UploadFailure"
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 10  # 10% failure rate
  treat_missing_data  = "notBreaching"
  
  # ✅ FIXED: Use rate, not absolute count
  metric_query {
    id          = "failure_rate"
    expression  = "(failures / (successes + failures)) * 100"
    label       = "S3 Upload Failure Rate (%)"
    return_data = true
  }
  
  metric_query {
    id = "failures"
    metric {
      metric_name = "S3UploadFailure"
      namespace   = "RetainWise/API"
      period      = 600  # 10 minutes
      stat        = "Sum"
    }
  }
  
  metric_query {
    id = "successes"
    metric {
      metric_name = "UploadSuccess"
      namespace   = "RetainWise/API"
      period      = 600
      stat        = "Sum"
    }
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-s3-upload-failures"
    Severity    = "critical"
    Environment = "production"
  }
}

# ===========================
# 7. DATABASE WRITE ERROR RATE (✅ FIXED - Now uses percentage)
# ===========================

resource "aws_cloudwatch_metric_alarm" "database_write_error_rate" {
  alarm_name          = "retainwise-database-write-error-rate"
  alarm_description   = <<EOF
CRITICAL: Database write error rate > 5% for 10 minutes.

CALCULATION: (errors / (errors + successes)) * 100

IMPACT: Predictions not saved, customer results lost.

RESOLUTION:
1. Check RDS instance status: aws rds describe-db-instances --db-instance-identifier retainwise-prod
2. Check RDS CPU/storage: CloudWatch → RDS metrics
3. Verify database connections: Check connection pool exhaustion
4. Check for schema issues: Recent migrations may have introduced bugs
5. Review application logs: Pattern might indicate specific table/query issue
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 5  # 5% error rate
  treat_missing_data  = "notBreaching"
  
  # ✅ FIXED: Use rate, not absolute count
  metric_query {
    id          = "error_rate"
    expression  = "(errors / (errors + successes)) * 100"
    label       = "Database Write Error Rate (%)"
    return_data = true
  }
  
  metric_query {
    id = "errors"
    metric {
      metric_name = "DatabaseWriteError"
      namespace   = "RetainWise/Database"
      period      = 600
      stat        = "Sum"
    }
  }
  
  metric_query {
    id = "successes"
    metric {
      metric_name = "PredictionsSaved"
      namespace   = "RetainWise/Database"
      period      = 600
      stat        = "Sum"
    }
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-database-write-errors"
    Severity    = "critical"
    Environment = "production"
  }
}

# ===========================
# 8. ML-SPECIFIC: PREDICTION CONFIDENCE LOW (NEW)
# ===========================

resource "aws_cloudwatch_metric_alarm" "prediction_confidence_low" {
  alarm_name          = "retainwise-prediction-confidence-low"
  alarm_description   = <<EOF
WARNING: Average prediction confidence < 70% for 1 hour.

IMPACT: Model may be degrading or input data distribution has changed.

ML-SPECIFIC: This indicates potential model drift or data quality issues.

RESOLUTION:
1. Check recent prediction confidence trend
2. Review input data quality (missing features, outliers)
3. Check for concept drift (real-world patterns changing)
4. Analyze feature distribution metrics
5. Consider model retraining if confidence remains low
EOF
  
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 12  # 12 periods × 5 min = 1 hour
  threshold           = 70  # 70% confidence
  treat_missing_data  = "notBreaching"
  
  metric_name = "PredictionConfidenceAvg"
  namespace   = "RetainWise/MLPipeline"
  period      = 300  # 5 minutes
  statistic   = "Average"
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-prediction-confidence"
    Severity    = "warning"
    Environment = "production"
    Category    = "ML"
  }
}

# ===========================
# 9. ML-SPECIFIC: MODEL LOADING FAILURES (NEW)
# ===========================

resource "aws_cloudwatch_metric_alarm" "model_loading_failures" {
  alarm_name          = "retainwise-model-loading-failures"
  alarm_description   = <<EOF
CRITICAL: Model failed to load from S3.

IMPACT: Worker cannot process predictions, complete outage.

ML-SPECIFIC: Model file may be corrupted or S3 permissions incorrect.

RESOLUTION:
1. Check if model file exists: aws s3 ls s3://retainwise-uploads/models/
2. Verify model file integrity (checksum)
3. Check IAM permissions for worker role (S3 GetObject)
4. Test downloading model manually
5. If model corrupted, restore from backup or retrain
EOF
  
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  treat_missing_data  = "notBreaching"
  
  metric_name = "ModelLoadError"
  namespace   = "RetainWise/Worker"
  period      = 60  # 1 minute
  statistic   = "Sum"
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-model-loading-failures"
    Severity    = "critical"
    Environment = "production"
    Category    = "ML"
  }
}

# ===========================
# 10. API UPLOAD SUCCESS RATE (✅ FIXED - Now uses percentage)
# ===========================

resource "aws_cloudwatch_metric_alarm" "api_upload_success_rate_low" {
  alarm_name          = "retainwise-api-upload-success-rate-low"
  alarm_description   = <<EOF
WARNING: API upload success rate < 95% for 10 minutes.

CALCULATION: (successes / (successes + errors)) * 100

IMPACT: Users experiencing frequent upload failures.

RESOLUTION:
1. Check recent error metrics: Review UploadRejected, S3UploadFailure, DatabaseWriteError
2. Identify most common failure type
3. Check backend logs for error patterns
4. If validation errors: May need to relax CSV format requirements
5. If infrastructure errors: Check S3/database health
EOF
  
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  threshold           = 95  # 95% success rate
  treat_missing_data  = "notBreaching"
  
  # ✅ FIXED: Use metric math for success rate
  metric_query {
    id          = "success_rate"
    expression  = "(successes / (successes + errors)) * 100"
    label       = "Upload Success Rate (%)"
    return_data = true
  }
  
  metric_query {
    id = "successes"
    metric {
      metric_name = "UploadSuccess"
      namespace   = "RetainWise/API"
      period      = 600  # 10 minutes
      stat        = "Sum"
    }
  }
  
  metric_query {
    id = "errors"
    metric {
      metric_name = "UploadUnexpectedError"
      namespace   = "RetainWise/API"
      period      = 600
      stat        = "Sum"
    }
  }
  
  alarm_actions = [aws_sns_topic.cloudwatch_alerts.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_alerts.arn]
  
  tags = {
    Name        = "retainwise-upload-success-rate"
    Severity    = "warning"
    Environment = "production"
  }
}

# ===========================
# OUTPUTS
# ===========================

output "cloudwatch_alarms" {
  description = "CloudWatch alarm ARNs"
  value = {
    sqs_queue_depth              = aws_cloudwatch_metric_alarm.sqs_queue_depth_high.arn
    sqs_message_age              = aws_cloudwatch_metric_alarm.sqs_message_age_high.arn
    dlq_messages                 = aws_cloudwatch_metric_alarm.dlq_messages_present.arn
    worker_error_rate            = aws_cloudwatch_metric_alarm.worker_error_rate_high.arn
    prediction_slow              = aws_cloudwatch_metric_alarm.prediction_processing_slow.arn
    s3_upload_failures           = aws_cloudwatch_metric_alarm.s3_upload_failure_rate.arn
    database_write_errors        = aws_cloudwatch_metric_alarm.database_write_error_rate.arn
    prediction_confidence_low    = aws_cloudwatch_metric_alarm.prediction_confidence_low.arn
    model_loading_failures       = aws_cloudwatch_metric_alarm.model_loading_failures.arn
    upload_success_rate_low      = aws_cloudwatch_metric_alarm.api_upload_success_rate_low.arn
  }
}

