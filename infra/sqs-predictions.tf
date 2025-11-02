# =====================================================
# SQS QUEUE FOR ML PREDICTION PROCESSING
# =====================================================
# Purpose: Async processing of churn predictions via ECS workers
# Design: Standard queue (high throughput) + DLQ (error handling)
# Security: Resource policies + IAM roles + VPC endpoints
# =====================================================

# ------------------------------------------------------
# MAIN PREDICTIONS QUEUE
# ------------------------------------------------------
resource "aws_sqs_queue" "predictions_queue" {
  name = "${var.environment}-retainwise-predictions-queue"

  # Message retention: 4 days
  message_retention_seconds = 345600

  # Visibility timeout: 5 minutes
  # Logic: Average CSV (1k rows) ~90s + buffer for model loading
  visibility_timeout_seconds = 300

  # Max message size: 256KB (default, sufficient for our metadata)
  max_message_size = 262144

  # Long polling: 20 seconds (reduces costs, improves efficiency)
  receive_wait_time_seconds = 20

  # Dead Letter Queue: 3 retries before DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.predictions_dlq.arn
    maxReceiveCount     = 3
  })

  # Server-side encryption: AWS managed keys
  sqs_managed_sse_enabled = true

  tags = {
    Name        = "${var.environment}-predictions-queue"
    Environment = var.environment
    Service     = "retainwise-ml"
    ManagedBy   = "terraform"
    Purpose     = "async-ml-predictions"
    CostCenter  = "ml-processing"
  }
}

# ------------------------------------------------------
# DEAD LETTER QUEUE (DLQ)
# ------------------------------------------------------
resource "aws_sqs_queue" "predictions_dlq" {
  name = "${var.environment}-retainwise-predictions-dlq"

  # DLQ retention: 14 days (longer for investigation)
  message_retention_seconds = 1209600

  visibility_timeout_seconds = 300
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  tags = {
    Name        = "${var.environment}-predictions-dlq"
    Environment = var.environment
    Service     = "retainwise-ml"
    ManagedBy   = "terraform"
    Purpose     = "failed-predictions-review"
  }
}

# ------------------------------------------------------
# SQS QUEUE POLICY (Resource-based)
# ------------------------------------------------------
# Security: Explicit principal ARNs (better than VPC conditions alone)
# ------------------------------------------------------
resource "aws_sqs_queue_policy" "predictions_queue_policy" {
  queue_url = aws_sqs_queue.predictions_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBackendSendMessages"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.backend_task_role.arn
        }
        Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
        Resource = aws_sqs_queue.predictions_queue.arn
      },
      {
        Sid    = "AllowWorkerReceiveMessages"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.worker_task_role.arn
        }
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.predictions_queue.arn
      },
      {
        Sid       = "DenyDangerousOperations"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "sqs:PurgeQueue",
          "sqs:DeleteQueue",
          "sqs:RemovePermission",
          "sqs:AddPermission",
          "sqs:SetQueueAttributes"
        ]
        Resource = aws_sqs_queue.predictions_queue.arn
      }
    ]
  })
}

# ------------------------------------------------------
# DLQ POLICY (Read-only for investigation)
# ------------------------------------------------------
resource "aws_sqs_queue_policy" "predictions_dlq_policy" {
  queue_url = aws_sqs_queue.predictions_dlq.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowWorkerReadDLQ"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.worker_task_role.arn
        }
        Action   = ["sqs:ReceiveMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.predictions_dlq.arn
      }
    ]
  })
}

# ------------------------------------------------------
# CLOUDWATCH ALARM: DLQ Monitoring
# ------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "dlq_messages_alarm" {
  alarm_name          = "${var.environment}-predictions-dlq-messages"
  alarm_description   = "Alert when DLQ has >5 messages (systemic failure)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.predictions_dlq.name
  }

  tags = {
    Name        = "${var.environment}-dlq-alarm"
    Environment = var.environment
    Service     = "retainwise-ml"
  }
}

# ------------------------------------------------------
# CLOUDWATCH ALARM: Queue Age
# ------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "queue_age_alarm" {
  alarm_name          = "${var.environment}-predictions-queue-age"
  alarm_description   = "Alert when oldest message >30min (workers down/backlogged)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1800
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.predictions_queue.name
  }

  tags = {
    Name        = "${var.environment}-queue-age-alarm"
    Environment = var.environment
    Service     = "retainwise-ml"
  }
}

# ------------------------------------------------------
# OUTPUTS
# ------------------------------------------------------
output "predictions_queue_url" {
  description = "URL of the main predictions queue"
  value       = aws_sqs_queue.predictions_queue.url
}

output "predictions_queue_arn" {
  description = "ARN of the main predictions queue"
  value       = aws_sqs_queue.predictions_queue.arn
}

output "predictions_dlq_url" {
  description = "URL of the predictions DLQ"
  value       = aws_sqs_queue.predictions_dlq.url
}

output "predictions_dlq_arn" {
  description = "ARN of the predictions DLQ"
  value       = aws_sqs_queue.predictions_dlq.arn
}
