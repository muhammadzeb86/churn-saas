# Route 53 Hosted Zone for retainwise.com
resource "aws_route53_zone" "main" {
  name = "retainwise.com"

  tags = {
    Name        = "retainwise.com"
    Environment = "production"
  }
}

# A record for the root domain (retainwise.com) pointing to ALB
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "retainwise.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# A record for www subdomain pointing to ALB
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.retainwise.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# A record for api subdomain pointing to ALB
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.retainwise.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# Health check for the API endpoint
resource "aws_route53_health_check" "api" {
  fqdn                     = "api.retainwise.com"
  port                     = 80
  type                     = "HTTP"
  resource_path            = "/health"
  failure_threshold        = 3
  request_interval         = 30
  enable_sni               = false
  measure_latency          = true

  tags = {
    Name = "retainwise-api-health-check"
  }
}

# CloudWatch alarm for health check failures
resource "aws_cloudwatch_metric_alarm" "api_health_check" {
  alarm_name          = "retainwise-api-health-check-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "This metric monitors api.retainwise.com health"
  alarm_actions       = [] # Add SNS topic ARN here if you want notifications

  dimensions = {
    HealthCheckId = aws_route53_health_check.api.id
  }

  tags = {
    Name = "retainwise-api-health-check-alarm"
  }
} 
