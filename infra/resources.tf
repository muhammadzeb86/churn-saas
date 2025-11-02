# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Archive Lambda function code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "lambda_ecs_scaling.py"
  output_path = "lambda_ecs_scaling.zip"
}

# Use existing VPC
data "aws_vpc" "existing" {
  id = "vpc-0c5ca9862562584d5"
}

# Use existing public subnets
data "aws_subnet" "public_1" {
  id = "subnet-0d539fd1a67a870ec"
}

data "aws_subnet" "public_2" {
  id = "subnet-03dcb4c3648af8f4d"
}

# Create private subnets in the existing VPC
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = data.aws_vpc.existing.id
  cidr_block        = "172.31.${96 + count.index * 16}.0/20"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "retainwise-private-subnet-${count.index + 1}"
  }
}

# S3 Bucket for uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "retainwise-uploads-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "retainwise-uploads"
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ECR Repository
resource "aws_ecr_repository" "backend" {
  name                 = "retainwise-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "retainwise-backend"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "retainwise-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "retainwise-cluster"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/retainwise-backend"
  retention_in_days = 7

  tags = {
    Name = "retainwise-backend-logs"
  }
}

# IAM Roles
resource "aws_iam_role" "ecs_task_execution" {
  name = "retainwise-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "retainwise-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# S3 access policy for ECS task
resource "aws_iam_policy" "s3_access" {
  name        = "retainwise-s3-access"
  description = "Allow ECS tasks to access S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "retainwise-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "retainwise-alb-sg"
  }
}

resource "aws_security_group" "ecs" {
  name        = "retainwise-ecs-sg"
  description = "Security group for ECS tasks"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "Allow ALB to access ECS tasks on 8000"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "retainwise-ecs-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "retainwise-rds-sg"
  description = "Security group for RDS instance"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "retainwise-rds-sg"
  }
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "retainwise-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "retainwise-db-subnet-group"
  }
}

# RDS Parameter Group
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "retainwise-postgres15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  tags = {
    Name = "retainwise-postgres15"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "retainwise-db"

  engine         = "postgres"
  engine_version = "15.13"
  instance_class = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp2"
  storage_encrypted     = true

  db_name  = "retainwise"
  username = "retainwiseuser"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  skip_final_snapshot      = true
  deletion_protection      = false
  delete_automated_backups = true

  publicly_accessible = false

  tags = {
    Name = "retainwise-db"
  }

  # Ignore password changes since RDS instance already exists with password set
  lifecycle {
    ignore_changes = [password]
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "retainwise-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [data.aws_subnet.public_1.id, data.aws_subnet.public_2.id]

  enable_deletion_protection = false
  idle_timeout               = 120 # 120 seconds for large file uploads

  tags = {
    Name = "retainwise-alb"
  }
}

resource "aws_lb_target_group" "backend" {
  name        = "retainwise-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.existing.id
  target_type = "ip"

  deregistration_delay = 30 # Graceful shutdown: 30 seconds for in-flight requests

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "8000"
    protocol            = "HTTP"
    timeout             = 5
  }

  tags = {
    Name = "retainwise-backend-tg"
  }
}

# HTTP listener removed - now handled by HTTPS redirect in https.tf

# ECS Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "retainwise-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "retainwise-backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.main.username}:${aws_db_instance.main.password}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
        },
        {
          name  = "S3_BUCKET"
          value = aws_s3_bucket.uploads.bucket
        },
        {
          name  = "AWS_REGION"
          value = "us-east-1"
        },
        {
          name  = "POWERBI_WORKSPACE_ID"
          value = "cb604b66-17ab-4831-b8b9-2e718c5cf3f5"
        },
        {
          name  = "POWERBI_REPORT_ID"
          value = "cda60607-7c02-47c5-a552-2b7c08a0d89c"
        },
        {
          name  = "POWERBI_CLIENT_ID"
          value = "d00fe407-6d4a-4d15-8213-63b898c0e762"
        },
        {
          name  = "POWERBI_TENANT_ID"
          value = "2830aab0-cdb4-4a6b-82e4-8d7856122010"
        },
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        }
      ]

      secrets = [
        {
          name      = "POWERBI_CLIENT_SECRET"
          valueFrom = "arn:aws:secretsmanager:us-east-1:908226940571:secret:POWERBI_CLIENT_SECRET"
        },
        {
          name      = "CLERK_WEBHOOK_SECRET"
          valueFrom = "arn:aws:secretsmanager:us-east-1:908226940571:secret:Clerk_Webhook"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = "us-east-1"
          awslogs-stream-prefix = "ecs"
        }
      }

      essential = true
    }
  ])

  tags = {
    Name = "retainwise-backend"
  }
}

# ECS Service
resource "aws_ecs_service" "backend" {
  name            = "retainwise-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # COST-SAVING DEV/TEST CONFIG: Using public subnets to avoid NAT Gateway costs
  # WARNING: This is NOT recommended for production use
  network_configuration {
    subnets          = ["subnet-0d539fd1a67a870ec", "subnet-03dcb4c3648af8f4d"] # Public subnets
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true # Assign public IPs to avoid NAT Gateway dependency
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "retainwise-backend"
    container_port   = 8000
  }

  # Health check grace period (time for new tasks to become healthy)
  health_check_grace_period_seconds = 120

  # Enable service discovery (optional)
  enable_execute_command = true

  # CRITICAL: Prevent Terraform from reverting task definition to old revisions
  # This allows CI/CD to manage task definitions while Terraform manages infrastructure
  lifecycle {
    ignore_changes = [
      task_definition,
      capacity_provider_strategy,
      desired_count
    ]
  }

  depends_on = [aws_lb_target_group.backend]

  tags = {
    Name        = "retainwise-service"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Lambda function for ECS scaling
resource "aws_lambda_function" "ecs_scaling" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "retainwise-ecs-scaling"
  role          = aws_iam_role.lambda_ecs_scaling.arn
  handler       = "lambda_ecs_scaling.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30

  environment {
    variables = {
      ECS_CLUSTER_NAME = aws_ecs_cluster.main.name
      ECS_SERVICE_NAME = aws_ecs_service.backend.name
    }
  }

  tags = {
    Name = "retainwise-ecs-scaling"
  }
}

# IAM role for Lambda function
resource "aws_iam_role" "lambda_ecs_scaling" {
  name = "retainwise-lambda-ecs-scaling-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Lambda to update ECS service
resource "aws_iam_policy" "lambda_ecs_scaling" {
  name        = "retainwise-lambda-ecs-scaling-policy"
  description = "Allow Lambda to update ECS service"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices"
        ]
        Resource = aws_ecs_service.backend.id
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Attach policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_ecs_scaling" {
  role       = aws_iam_role.lambda_ecs_scaling.name
  policy_arn = aws_iam_policy.lambda_ecs_scaling.arn
}

# EventBridge rule to scale down ECS service (00:01 AM UK time)
resource "aws_cloudwatch_event_rule" "ecs_scale_down" {
  name                = "retainwise-ecs-scale-down"
  description         = "Scale down ECS service to 0 tasks at 00:01 AM UK time"
  schedule_expression = "cron(1 0 * * ? *)" # 00:01 AM UTC (01:01 AM BST in summer)

  tags = {
    Name = "retainwise-ecs-scale-down"
  }
}

# EventBridge rule to scale up ECS service (5:00 PM UK time)
resource "aws_cloudwatch_event_rule" "ecs_scale_up" {
  name                = "retainwise-ecs-scale-up"
  description         = "Scale up ECS service to 1 task at 5:00 PM UK time"
  schedule_expression = "cron(0 17 * * ? *)" # 17:00 UTC (18:00 BST in summer)

  tags = {
    Name = "retainwise-ecs-scale-up"
  }
}

# EventBridge target for scale down
resource "aws_cloudwatch_event_target" "ecs_scale_down_target" {
  rule      = aws_cloudwatch_event_rule.ecs_scale_down.name
  target_id = "ECSScaleDown"
  arn       = aws_lambda_function.ecs_scaling.arn

  input = jsonencode({
    desired_count = 0
  })
}

# EventBridge target for scale up
resource "aws_cloudwatch_event_target" "ecs_scale_up_target" {
  rule      = aws_cloudwatch_event_rule.ecs_scale_up.name
  target_id = "ECSScaleUp"
  arn       = aws_lambda_function.ecs_scaling.arn

  input = jsonencode({
    desired_count = 1
  })
}

# Lambda permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge_scale_down" {
  statement_id  = "AllowExecutionFromEventBridgeScaleDown"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ecs_scaling.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ecs_scale_down.arn
}

resource "aws_lambda_permission" "allow_eventbridge_scale_up" {
  statement_id  = "AllowExecutionFromEventBridgeScaleUp"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ecs_scaling.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ecs_scale_up.arn
}

# NAT Gateway and EIP - COMMENTED OUT TO SAVE COSTS
# Uncomment when you need ECS tasks to run in private subnets

# resource "aws_eip" "nat" {
#   domain = "vpc"
#   tags = {
#     Name = "retainwise-nat-eip"
#   }
# }

# resource "aws_nat_gateway" "main" {
#   allocation_id = aws_eip.nat.id
#   subnet_id     = "subnet-0d539fd1a67a870ec"
#   tags = {
#     Name = "retainwise-nat-gw"
#   }
# }

# resource "aws_route" "private_nat_gateway" {
#   route_table_id         = "rtb-01bd6333a3b7b43e4"
#   destination_cidr_block = "0.0.0.0/0"
#   nat_gateway_id         = aws_nat_gateway.main.id
# } 
