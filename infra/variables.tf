# =====================================================
# TERRAFORM VARIABLES
# =====================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "github_repository" {
  description = "GitHub repository in format owner/repo"
  type        = string
  default     = "muhammadzeb86/churn-saas"
}

variable "db_password" {
  description = "Database password (only needed for new RDS instances)"
  type        = string
  sensitive   = true
  default     = ""  # Empty string for existing RDS (password already set)
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "vpc_id" {
  description = "VPC ID for resource restrictions"
  type        = string
  default     = "vpc-0c5ca9862562584d5" # Your existing VPC

  validation {
    condition     = can(regex("^vpc-", var.vpc_id))
    error_message = "VPC ID must start with 'vpc-'"
  }
}

# =====================================================
# SQS CONFIGURATION VARIABLES
# =====================================================

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 300

  validation {
    condition     = var.sqs_visibility_timeout >= 30 && var.sqs_visibility_timeout <= 43200
    error_message = "Visibility timeout must be between 30 seconds and 12 hours"
  }
}

variable "sqs_message_retention" {
  description = "SQS message retention period in seconds"
  type        = number
  default     = 345600

  validation {
    condition     = var.sqs_message_retention >= 60 && var.sqs_message_retention <= 1209600
    error_message = "Message retention must be between 60 seconds and 14 days"
  }
}

variable "sqs_dlq_max_receive_count" {
  description = "Number of receive attempts before sending to DLQ"
  type        = number
  default     = 3

  validation {
    condition     = var.sqs_dlq_max_receive_count >= 1 && var.sqs_dlq_max_receive_count <= 1000
    error_message = "Max receive count must be between 1 and 1000"
  }
}

variable "sqs_receive_wait_time" {
  description = "SQS long polling wait time in seconds"
  type        = number
  default     = 20

  validation {
    condition     = var.sqs_receive_wait_time >= 0 && var.sqs_receive_wait_time <= 20
    error_message = "Receive wait time must be between 0 and 20 seconds"
  }
}

variable "enable_sqs_encryption" {
  description = "Enable server-side encryption for SQS queues"
  type        = bool
  default     = true
}

variable "dlq_alarm_threshold" {
  description = "Number of DLQ messages before triggering alarm"
  type        = number
  default     = 5

  validation {
    condition     = var.dlq_alarm_threshold > 0
    error_message = "DLQ alarm threshold must be greater than 0"
  }
}

variable "queue_age_alarm_threshold" {
  description = "Age of oldest message in seconds before alarming"
  type        = number
  default     = 1800

  validation {
    condition     = var.queue_age_alarm_threshold >= 300
    error_message = "Queue age alarm threshold must be at least 5 minutes"
  }
}
