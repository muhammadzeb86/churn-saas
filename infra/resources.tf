# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

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
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  skip_final_snapshot       = true
  deletion_protection       = false
  delete_automated_backups  = true
  
  publicly_accessible = false

  tags = {
    Name = "retainwise-db"
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

  tags = {
    Name = "retainwise-alb"
  }
}

resource "aws_lb_target_group" "backend" {
  name     = "retainwise-backend-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.existing.id
  target_type = "ip"

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

resource "aws_lb_listener" "backend" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

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
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = ["subnet-0fbe1d48a7085fa2d", "subnet-0c3068ad1b87abac0"]
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "retainwise-backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.backend]

  tags = {
    Name = "retainwise-service"
  }
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