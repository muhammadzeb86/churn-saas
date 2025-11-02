# IAM Restrictions for CI/CD Task Definition Management
# Ensures only CI/CD pipeline can modify task definitions

# IAM Policy for CI/CD pipeline - RESTRICTED permissions
resource "aws_iam_policy" "cicd_ecs_deployment" {
  name        = "retainwise-cicd-ecs-deployment-restricted"
  description = "Restricted permissions for CI/CD to manage ECS deployments only"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:RegisterTaskDefinition"
        ]
        Resource = [
          aws_ecs_service.backend.id,
          aws_ecs_service.retainwise_worker.id,
          "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/retainwise-backend:*",
          "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/retainwise-worker:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:DescribeTasks",
          "ecs:RunTask"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn,
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/prod-retainwise-backend-task-role",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/prod-retainwise-worker-task-role"
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "elbv2:DescribeLoadBalancers"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:GetParameter"
        ]
        Resource = aws_ssm_parameter.golden_task_definition.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.backend.arn,
          aws_cloudwatch_log_group.worker.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs",
          "ec2:DescribeVpcAttribute",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeRouteTables",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNatGateways"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = var.aws_region
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = var.aws_region
          }
        }
      }
    ]
  })

  tags = {
    Name        = "retainwise-cicd-ecs-deployment-restricted"
    Environment = "production"
    Purpose     = "cicd-deployment-restrictions"
  }
}

# IAM Role for CI/CD (GitHub Actions)
resource "aws_iam_role" "cicd_ecs_deployment" {
  name = "retainwise-cicd-ecs-deployment-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "retainwise-cicd-ecs-deployment-role"
    Environment = "production"
    Purpose     = "cicd-deployment"
  }
}

# Attach restricted policy to CI/CD role
resource "aws_iam_role_policy_attachment" "cicd_ecs_deployment" {
  role       = aws_iam_role.cicd_ecs_deployment.name
  policy_arn = aws_iam_policy.cicd_ecs_deployment.arn
}

# DENY policy for human users - prevents accidental task definition changes
resource "aws_iam_policy" "deny_ecs_task_definition_changes" {
  name        = "retainwise-deny-ecs-td-changes"
  description = "Denies task definition changes for human users"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = [
          "ecs:UpdateService"
        ]
        Resource = [
          aws_ecs_service.backend.id,
          aws_ecs_service.retainwise_worker.id
        ]
        Condition = {
          StringNotLike = {
            "aws:userid" = "*:${aws_iam_role.cicd_ecs_deployment.unique_id}:*"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "retainwise-deny-ecs-td-changes"
    Environment = "production"
    Purpose     = "security-restriction"
  }
}

# Output CI/CD role ARN for GitHub Actions
output "cicd_deployment_role_arn" {
  description = "IAM role ARN for CI/CD deployments"
  value       = aws_iam_role.cicd_ecs_deployment.arn
}

output "cicd_deployment_role_name" {
  description = "IAM role name for CI/CD deployments"
  value       = aws_iam_role.cicd_ecs_deployment.name
}
