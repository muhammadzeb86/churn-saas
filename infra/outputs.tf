output "s3_bucket_name" {
  description = "Name of the S3 bucket for uploads"
  value       = aws_s3_bucket.uploads.bucket
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "load_balancer_dns" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = data.aws_vpc.existing.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = [data.aws_subnet.public_1.id, data.aws_subnet.public_2.id]
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "lambda_ecs_scaling_function_name" {
  description = "Name of the Lambda function for ECS scaling"
  value       = aws_lambda_function.ecs_scaling.function_name
}

output "lambda_ecs_scaling_function_arn" {
  description = "ARN of the Lambda function for ECS scaling"
  value       = aws_lambda_function.ecs_scaling.arn
}

output "ecs_scale_down_rule_arn" {
  description = "ARN of the EventBridge rule for scaling down ECS"
  value       = aws_cloudwatch_event_rule.ecs_scale_down.arn
}

# Route 53 outputs
output "route53_zone_id" {
  description = "Route 53 hosted zone ID for retainwise.com"
  value       = aws_route53_zone.main.zone_id
}

output "route53_name_servers" {
  description = "Route 53 name servers for retainwise.com"
  value       = aws_route53_zone.main.name_servers
}

output "ssl_certificate_arn" {
  description = "ARN of the SSL certificate"
  value       = aws_acm_certificate.main.arn
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.arn
}

output "route53_zone_arn" {
  description = "Route 53 hosted zone ARN"
  value       = aws_route53_zone.main.arn
}

output "api_health_check_id" {
  description = "Route 53 health check ID for API endpoint"
  value       = aws_route53_health_check.api.id
}

output "ecs_scale_up_rule_arn" {
  description = "ARN of the EventBridge rule for scaling up ECS"
  value       = aws_cloudwatch_event_rule.ecs_scale_up.arn
} 