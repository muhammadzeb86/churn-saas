# SQS Queue for ML Predictions Processing
resource "aws_sqs_queue" "predictions" {
  name                       = "predictions-queue"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 1209600  # 14 days
  max_message_size          = 262144    # 256 KB
  delay_seconds             = 0
  receive_wait_time_seconds = 0

  tags = {
    Name        = "predictions-queue"
    Environment = "production"
    Service     = "retainwise-backend"
  }
}

# IAM Policy Document for SQS SendMessage
data "aws_iam_policy_document" "sqs_send_message" {
  statement {
    sid    = "AllowSQSSendMessage"
    effect = "Allow"
    
    actions = [
      "sqs:SendMessage"
    ]
    
    resources = [
      aws_sqs_queue.predictions.arn
    ]
  }
}

# IAM Policy for SQS SendMessage
resource "aws_iam_policy" "backend_sqs_send" {
  name        = "retainwise-backend-sqs-send"
  description = "Allow backend to send messages to predictions SQS queue"
  policy      = data.aws_iam_policy_document.sqs_send_message.json

  tags = {
    Name        = "retainwise-backend-sqs-send"
    Environment = "production"
    Service     = "retainwise-backend"
  }
}

# Attach SQS policy to existing backend ECS task role
resource "aws_iam_role_policy_attachment" "backend_sqs_send" {
  role       = "retainwise-backend-task-role"  # Replace with actual role name
  policy_arn = aws_iam_policy.backend_sqs_send.arn
}

# Output values for reference
output "predictions_queue_url" {
  description = "URL of the predictions SQS queue"
  value       = aws_sqs_queue.predictions.url
}

output "predictions_queue_arn" {
  description = "ARN of the predictions SQS queue"
  value       = aws_sqs_queue.predictions.arn
}

output "backend_sqs_policy_arn" {
  description = "ARN of the backend SQS send policy"
  value       = aws_iam_policy.backend_sqs_send.arn
} 