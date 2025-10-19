# Route 53 Hosted Zone for retainwiseanalytics.com
resource "aws_route53_zone" "main" {
  name = "retainwiseanalytics.com"

  tags = {
    Name        = "retainwiseanalytics.com"
    Environment = "production"
  }
}

# A record for the root domain (retainwiseanalytics.com) pointing to ALB
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "retainwiseanalytics.com"
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
  name    = "www.retainwiseanalytics.com"
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
  name    = "api.retainwiseanalytics.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# A record for backend subdomain pointing to ALB (legacy/alternative endpoint)
resource "aws_route53_record" "backend" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "backend.retainwiseanalytics.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# Health check for the API endpoint
resource "aws_route53_health_check" "api" {
  fqdn                     = "api.retainwiseanalytics.com"
  port                     = 80
  type                     = "HTTP"
  resource_path            = "/health"
  failure_threshold        = 3
  request_interval         = 30
  enable_sni               = false
  measure_latency          = true

  tags = {
    Name = "retainwiseanalytics-api-health-check"
  }
}

# CNAME record for app subdomain pointing to Vercel
resource "aws_route53_record" "app" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["ecf0fa7ec7f02e4f.vercel-dns-017.com"]
}

# Clerk DNS records for authentication
resource "aws_route53_record" "clerk_frontend" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "clerk.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["frontend-api.clerk.services"]
}

resource "aws_route53_record" "clerk_accounts" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "accounts.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["accounts.clerk.services"]
}

resource "aws_route53_record" "clerk_email" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "clkmail.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["mail.eoqmz4ql39r.clerk.services"]
}

resource "aws_route53_record" "clerk_dkim1" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "clk._domainkey.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["dkim1.eoqmz4ql39r.clerk.services"]
}

resource "aws_route53_record" "clerk_dkim2" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "clk2._domainkey.retainwiseanalytics.com"
  type    = "CNAME"
  ttl     = "300"
  records = ["dkim2.eoqmz4ql39r.clerk.services"]
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
  alarm_description   = "This metric monitors api.retainwiseanalytics.com health"
  alarm_actions       = [] # Add SNS topic ARN here if you want notifications

  dimensions = {
    HealthCheckId = aws_route53_health_check.api.id
  }

  tags = {
    Name = "retainwise-api-health-check-alarm"
  }
} 
