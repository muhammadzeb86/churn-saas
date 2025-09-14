# Secrets Manager IAM policy for ECS task role
data "aws_iam_policy_document" "secrets_manager_access" {
  statement {
    sid    = "AllowSecretsManagerAccess"
    effect = "Allow"
    
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:*"
    ]
  }
}

# Create IAM policy for Secrets Manager access
resource "aws_iam_policy" "secrets_manager_access" {
  name        = "retainwise-secrets-manager-access"
  description = "Allow ECS task to access Secrets Manager secrets"
  policy      = data.aws_iam_policy_document.secrets_manager_access.json

  tags = {
    Name        = "retainwise-secrets-manager-access"
    Environment = var.environment
    Service     = "retainwise-backend"
  }
}

# Attach Secrets Manager policy to ECS task role
resource "aws_iam_role_policy_attachment" "ecs_task_secrets_manager" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.secrets_manager_access.arn
} 