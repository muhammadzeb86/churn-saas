# =====================================================
# IAM ROLES & POLICIES FOR SQS ACCESS
# =====================================================
# Principle: Least Privilege - Explicit role separation
# Backend: Send only | Worker: Receive/Delete only
# =====================================================

# ------------------------------------------------------
# BACKEND TASK ROLE
# ------------------------------------------------------
resource "aws_iam_role" "backend_task_role" {
  name = "${var.environment}-retainwise-backend-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "${var.environment}-backend"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-backend-task-role"
    Environment = var.environment
    Service     = "retainwise-backend"
    ManagedBy   = "terraform"
  }
}

# ------------------------------------------------------
# WORKER TASK ROLE
# ------------------------------------------------------
resource "aws_iam_role" "worker_task_role" {
  name = "${var.environment}-retainwise-worker-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "${var.environment}-worker"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-worker-task-role"
    Environment = var.environment
    Service     = "retainwise-worker"
    ManagedBy   = "terraform"
  }
}

# ------------------------------------------------------
# POLICY: Backend SQS Send
# ------------------------------------------------------
resource "aws_iam_policy" "sqs_send_policy" {
  name        = "${var.environment}-retainwise-sqs-send"
  description = "Allow backend API to send messages to predictions queue"
  path        = "/retainwise/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSendToPredictionsQueue"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [aws_sqs_queue.predictions_queue.arn]
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-sqs-send-policy"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ------------------------------------------------------
# POLICY: Worker SQS Receive/Delete
# ------------------------------------------------------
resource "aws_iam_policy" "sqs_worker_policy" {
  name        = "${var.environment}-retainwise-sqs-worker"
  description = "Allow worker to receive and delete messages from predictions queue"
  path        = "/retainwise/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowWorkerQueueOperations"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.predictions_queue.arn,
          aws_sqs_queue.predictions_dlq.arn
        ]
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-sqs-worker-policy"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ------------------------------------------------------
# S3 ACCESS POLICY (Backend and Worker need S3 access)
# ------------------------------------------------------
resource "aws_iam_policy" "s3_full_access" {
  name        = "${var.environment}-retainwise-s3-access"
  description = "Allow access to RetainWise S3 bucket for uploads and predictions"
  path        = "/retainwise/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::retainwise-uploads-${data.aws_caller_identity.current.account_id}",
          "arn:aws:s3:::retainwise-uploads-${data.aws_caller_identity.current.account_id}/*"
        ]
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-s3-access-policy"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ------------------------------------------------------
# ATTACH POLICIES TO ROLES
# ------------------------------------------------------
resource "aws_iam_role_policy_attachment" "backend_sqs_send" {
  role       = aws_iam_role.backend_task_role.name
  policy_arn = aws_iam_policy.sqs_send_policy.arn
}

resource "aws_iam_role_policy_attachment" "backend_s3_access" {
  role       = aws_iam_role.backend_task_role.name
  policy_arn = aws_iam_policy.s3_full_access.arn
}

resource "aws_iam_role_policy_attachment" "worker_sqs_receive" {
  role       = aws_iam_role.worker_task_role.name
  policy_arn = aws_iam_policy.sqs_worker_policy.arn
}

resource "aws_iam_role_policy_attachment" "worker_s3_access" {
  role       = aws_iam_role.worker_task_role.name
  policy_arn = aws_iam_policy.s3_full_access.arn
}

# ------------------------------------------------------
# ATTACH AWS MANAGED POLICIES (ECS Task Execution)
# ------------------------------------------------------
resource "aws_iam_role_policy_attachment" "backend_execution_role" {
  role       = aws_iam_role.backend_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "worker_execution_role" {
  role       = aws_iam_role.worker_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------
# OUTPUTS
# ------------------------------------------------------
output "backend_task_role_arn" {
  description = "ARN of backend ECS task role"
  value       = aws_iam_role.backend_task_role.arn
}

output "worker_task_role_arn" {
  description = "ARN of worker ECS task role"
  value       = aws_iam_role.worker_task_role.arn
}

output "sqs_send_policy_arn" {
  description = "ARN of SQS send policy"
  value       = aws_iam_policy.sqs_send_policy.arn
}

output "sqs_worker_policy_arn" {
  description = "ARN of SQS worker policy"
  value       = aws_iam_policy.sqs_worker_policy.arn
}

