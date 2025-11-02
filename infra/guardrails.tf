# EventBridge Guardrails for Task Definition Drift Detection
# Automatically detects and corrects task definition drift

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "retainwise-alerts"

  tags = {
    Name        = "retainwise-alerts"
    Environment = "production"
    Purpose     = "drift-alerts"
  }
}

# Lambda function for TD drift detection
resource "aws_lambda_function" "td_guardrail" {
  filename      = "lambda_td_guardrail.zip"
  function_name = "retainwise-td-guardrail"
  role          = aws_iam_role.lambda_td_guardrail.arn
  handler       = "lambda_td_guardrail.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60

  environment {
    variables = {
      CLUSTER_NAME = "retainwise-cluster"
      SERVICE_NAME = "retainwise-service"
    }
  }

  tags = {
    Name        = "retainwise-td-guardrail"
    Environment = "production"
    Purpose     = "drift-detection"
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_td_guardrail" {
  name = "retainwise-lambda-td-guardrail-role"

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

  tags = {
    Name = "retainwise-lambda-td-guardrail-role"
  }
}

# IAM policy for Lambda permissions
resource "aws_iam_policy" "lambda_td_guardrail" {
  name = "retainwise-lambda-td-guardrail-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:UpdateService"
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
          aws_iam_role.ecs_task.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = aws_ssm_parameter.golden_task_definition.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "lambda_td_guardrail" {
  role       = aws_iam_role.lambda_td_guardrail.name
  policy_arn = aws_iam_policy.lambda_td_guardrail.arn
}

# EventBridge rule to trigger guardrail every 30 minutes (reduced frequency to avoid conflicts with CI/CD)
resource "aws_cloudwatch_event_rule" "td_drift_check" {
  name                = "retainwise-td-drift-check"
  description         = "Check for task definition drift every 30 minutes (alert-only mode)"
  schedule_expression = "rate(30 minutes)"

  tags = {
    Name        = "retainwise-td-drift-check"
    Environment = "production"
    Mode        = "alert-only"
  }
}

# EventBridge target
resource "aws_cloudwatch_event_target" "td_drift_check" {
  rule      = aws_cloudwatch_event_rule.td_drift_check.name
  target_id = "RetainWiseTDGuardrail"
  arn       = aws_lambda_function.td_guardrail.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_td_guardrail" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.td_guardrail.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.td_drift_check.arn
}

# Outputs
output "sns_topic_arn" {
  description = "SNS topic ARN for drift alerts"
  value       = aws_sns_topic.alerts.arn
}

output "guardrail_lambda_arn" {
  description = "Lambda function ARN for TD guardrail"
  value       = aws_lambda_function.td_guardrail.arn
}
