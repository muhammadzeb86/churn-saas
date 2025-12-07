# SNS Topic for CloudWatch Alarms
#
# Design:
# 1. Single SNS topic for all alerts (simplifies subscription management)
# 2. Email subscription for ops team (extensible to Slack/PagerDuty later)
# 3. Delivery retry policy (ensure alerts aren't lost)
# 4. DLQ for failed deliveries (audit trail)
#
# Author: AI Assistant
# Date: December 3, 2025

resource "aws_sns_topic" "cloudwatch_alerts" {
  name         = "retainwise-cloudwatch-alerts"
  display_name = "RetainWise CloudWatch Alerts"
  
  # Delivery policy: Retry failed deliveries
  delivery_policy = jsonencode({
    http = {
      defaultHealthyRetryPolicy = {
        minDelayTarget     = 20
        maxDelayTarget     = 20
        numRetries         = 3
        numMaxDelayRetries = 0
        numNoDelayRetries  = 0
        numMinDelayRetries = 0
        backoffFunction    = "linear"
      }
      disableSubscriptionOverrides = false
    }
  })
  
  tags = {
    Name        = "retainwise-cloudwatch-alerts"
    Environment = "production"
    Purpose     = "Alert notifications for ML pipeline"
  }
}

# DLQ for failed SNS deliveries
resource "aws_sqs_queue" "sns_dlq" {
  name = "retainwise-sns-dlq"
  
  # Retain failed deliveries for 14 days (audit trail)
  message_retention_seconds = 1209600  # 14 days
  
  tags = {
    Name        = "retainwise-sns-dlq"
    Environment = "production"
  }
}

# SNS topic policy (allow CloudWatch to publish)
resource "aws_sns_topic_policy" "cloudwatch_alerts_policy" {
  arn = aws_sns_topic.cloudwatch_alerts.arn
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.cloudwatch_alerts.arn
      }
    ]
  })
}

# Email subscription (MANUAL CONFIRMATION REQUIRED)
# After applying Terraform, support team must click confirmation link in email

variable "alert_email" {
  description = "Email address to receive CloudWatch alerts"
  type        = string
  default     = "support@retainwiseanalytics.com"
}

resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.cloudwatch_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
  
  # Redrive policy: Send failed deliveries to DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.sns_dlq.arn
  })
}

# (Optional) Slack subscription for future use
# Requires Slack webhook setup first

# variable "slack_webhook_url" {
#   description = "Slack webhook URL for alert notifications"
#   type        = string
#   default     = ""
#   sensitive   = true
# }

# resource "aws_sns_topic_subscription" "slack_alerts" {
#   count     = var.slack_webhook_url != "" ? 1 : 0
#   topic_arn = aws_sns_topic.cloudwatch_alerts.arn
#   protocol  = "https"
#   endpoint  = var.slack_webhook_url
# }

# Output SNS topic ARN for reference
# Note: Named "cloudwatch_alerts_sns_topic_arn" to avoid conflict with guardrails.tf output
output "cloudwatch_alerts_sns_topic_arn" {
  description = "ARN of SNS topic for CloudWatch alerts"
  value       = aws_sns_topic.cloudwatch_alerts.arn
}

output "cloudwatch_alerts_sns_topic_name" {
  description = "Name of SNS topic for CloudWatch alerts"
  value       = aws_sns_topic.cloudwatch_alerts.name
}

