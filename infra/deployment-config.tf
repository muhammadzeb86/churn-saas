# ECS Deployment Configuration
# Production-grade deployment settings with circuit breaker and rolling updates

# CloudWatch Log Group for deployment events
resource "aws_cloudwatch_log_group" "deployment_events" {
  name              = "/aws/ecs/retainwise-deployment-events"
  retention_in_days = 30

  tags = {
    Name        = "retainwise-deployment-events"
    Environment = "production"
    Purpose     = "deployment-monitoring"
  }
}

# CloudWatch Alarm for deployment failures
resource "aws_cloudwatch_metric_alarm" "deployment_failure" {
  alarm_name          = "retainwise-deployment-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DeploymentFailures"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors ECS deployment failures"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ServiceName = "retainwise-service"
    ClusterName = "retainwise-cluster"
  }

  tags = {
    Name        = "retainwise-deployment-failure"
    Environment = "production"
  }
}

# CloudWatch Alarm for service health
resource "aws_cloudwatch_metric_alarm" "service_health" {
  alarm_name          = "retainwise-service-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors ECS service health"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ServiceName = "retainwise-service"
    ClusterName = "retainwise-cluster"
  }

  tags = {
    Name        = "retainwise-service-health"
    Environment = "production"
  }
}

# Output deployment configuration
output "deployment_configuration" {
  description = "ECS deployment configuration details"
  value = {
    maximum_percent           = 200
    minimum_healthy_percent   = 50
    circuit_breaker_enabled   = true
    circuit_breaker_rollback  = true
    health_check_grace_period = 120
  }
}
