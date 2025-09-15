# ECS Worker Service for Prediction Processing

# IAM Policy Document for Worker (SQS + S3 permissions)
data "aws_iam_policy_document" "worker_permissions" {
  # SQS permissions for worker
  statement {
    sid    = "AllowSQSWorkerOperations"
    effect = "Allow"
    
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility"
    ]
    
    resources = [
      aws_sqs_queue.predictions.arn
    ]
  }
  
  # S3 permissions for worker (read input, write output)
  statement {
    sid    = "AllowS3WorkerOperations"
    effect = "Allow"
    
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    
    resources = [
      "${data.aws_s3_bucket.uploads.arn}/*"
    ]
  }
  
  # S3 bucket listing (for validation)
  statement {
    sid    = "AllowS3BucketListing"
    effect = "Allow"
    
    actions = [
      "s3:ListBucket"
    ]
    
    resources = [
      data.aws_s3_bucket.uploads.arn
    ]
  }
}

# IAM Policy for Worker
resource "aws_iam_policy" "worker_permissions" {
  name        = "retainwise-worker-permissions"
  description = "Permissions for RetainWise prediction worker"
  policy      = data.aws_iam_policy_document.worker_permissions.json

  tags = {
    Name        = "retainwise-worker-permissions"
    Environment = "production"
    Service     = "retainwise-worker"
  }
}

# Attach worker permissions to existing ECS task role
resource "aws_iam_role_policy_attachment" "worker_permissions" {
  role       = "retainwise-ecs-task-role"  # Reuse existing task role
  policy_arn = aws_iam_policy.worker_permissions.arn
}

# ECS Task Definition for Worker
resource "aws_ecs_task_definition" "retainwise_worker" {
  family                   = "retainwise-worker"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = 256
  memory                  = 512
  
  # Use same execution role as backend
  execution_role_arn = data.aws_iam_role.ecs_execution_role.arn
  task_role_arn      = data.aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "worker"
      image = "${aws_ecr_repository.backend.repository_url}:latest"
      
      # Worker command override
      command = ["python", "-m", "backend.worker_main"]
      
      # Environment variables
      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "PREDICTIONS_QUEUE_URL"
          value = aws_sqs_queue.predictions.url
        },
        {
          name  = "S3_BUCKET"
          value = data.aws_s3_bucket.uploads.bucket
        }
      ]
      
      # Database URL from Secrets Manager
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.database_url.arn
        }
      ]
      
      # CloudWatch Logs
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      # Resource limits
      cpu    = 256
      memory = 512
      
      # Health check (optional - worker doesn't expose ports)
      essential = true
    }
  ])

  tags = {
    Name        = "retainwise-worker"
    Environment = "production"
    Service     = "retainwise-worker"
  }
}

# CloudWatch Log Group for Worker
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/retainwise-worker"
  retention_in_days = 7

  tags = {
    Name        = "retainwise-worker-logs"
    Environment = "production"
    Service     = "retainwise-worker"
  }
}

# ECS Service for Worker
resource "aws_ecs_service" "retainwise_worker" {
  name            = "retainwise-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.retainwise_worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  
  # Network configuration
  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
  
  # Deployment configuration
  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 0  # Allow complete replacement for workers
  }
  
  # Depend on queue and IAM policies
  depends_on = [
    aws_sqs_queue.predictions,
    aws_iam_role_policy_attachment.worker_permissions
  ]

  tags = {
    Name        = "retainwise-worker"
    Environment = "production"
    Service     = "retainwise-worker"
  }
}

# Dead Letter Queue for failed predictions (optional but recommended)
resource "aws_sqs_queue" "predictions_dlq" {
  name = "predictions-dlq"
  
  # Retain failed messages for investigation
  message_retention_seconds = 1209600  # 14 days

  tags = {
    Name        = "predictions-dlq"
    Environment = "production"
    Service     = "retainwise-backend"
  }
}

# Update main queue to use DLQ
resource "aws_sqs_queue_redrive_policy" "predictions_redrive" {
  queue_url = aws_sqs_queue.predictions.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.predictions_dlq.arn
    maxReceiveCount     = 3  # Retry 3 times before sending to DLQ
  })
}

# Outputs
output "worker_service_name" {
  description = "Name of the worker ECS service"
  value       = aws_ecs_service.retainwise_worker.name
}

output "worker_log_group" {
  description = "CloudWatch log group for worker"
  value       = aws_cloudwatch_log_group.worker.name
}

output "predictions_dlq_url" {
  description = "URL of the predictions dead letter queue"
  value       = aws_sqs_queue.predictions_dlq.url
} 