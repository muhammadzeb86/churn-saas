# Golden Task Definition Storage
# Stores the authoritative task definition ARN in SSM Parameter Store
# Updated by CI/CD pipeline after each successful deployment

resource "aws_ssm_parameter" "golden_task_definition" {
  name  = "/retainwise/golden-task-definition"
  type  = "String"
  value = aws_ecs_task_definition.backend.arn

  description = "Golden task definition ARN - authoritative source of truth for production deployments"
  
  tags = {
    Name        = "retainwise-golden-td"
    Environment = "production"
    ManagedBy   = "terraform"
    Purpose     = "deployment-guardrail"
  }
}

# Output the golden TD ARN for CI/CD pipeline
output "golden_task_definition_arn" {
  description = "Golden task definition ARN stored in SSM Parameter Store"
  value       = aws_ssm_parameter.golden_task_definition.arn
}

output "golden_task_definition_parameter_name" {
  description = "SSM Parameter name for golden task definition"
  value       = aws_ssm_parameter.golden_task_definition.name
}
