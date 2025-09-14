# IAM Changes for SQS Predictions Queue

## Resources Created

### SQS Queue
- **Resource Name:** `aws_sqs_queue.predictions`
- **Queue Name:** `predictions-queue`
- **Expected ARN:** `arn:aws:sqs:us-east-1:908226940571:predictions-queue`
- **Expected URL:** `https://sqs.us-east-1.amazonaws.com/908226940571/predictions-queue`

### IAM Policy
- **Resource Name:** `aws_iam_policy.backend_sqs_send`
- **Policy Name:** `retainwise-backend-sqs-send`
- **Expected ARN:** `arn:aws:iam::908226940571:policy/retainwise-backend-sqs-send`

### IAM Policy Attachment
- **Resource Name:** `aws_iam_role_policy_attachment.backend_sqs_send`
- **Target Role:** `retainwise-ecs-task-role` *(verified actual role name)*
- **Policy ARN:** References `aws_iam_policy.backend_sqs_send.arn`

## Manual Steps Required

### 1. Verify ECS Task Role Name
Before applying Terraform, confirm the actual ECS task role name:
```bash
aws iam list-roles --query "Roles[?contains(RoleName, 'retainwise') && contains(RoleName, 'task')].RoleName"
```

### 2. ✅ Terraform Updated
The role name has been updated in `infra/sqs-predictions.tf`:
```hcl
resource "aws_iam_role_policy_attachment" "backend_sqs_send" {
  role       = "retainwise-ecs-task-role"  # Verified actual role name
  policy_arn = aws_iam_policy.backend_sqs_send.arn
}
```

### 3. Apply Infrastructure
```bash
cd infra
terraform plan
terraform apply
```

### 4. Update ECS Task Definition
Add environment variables to ECS task definition:
```json
{
  "name": "PREDICTIONS_QUEUE_URL",
  "value": "https://sqs.us-east-1.amazonaws.com/908226940571/predictions-queue"
},
{
  "name": "AWS_REGION",
  "value": "us-east-1"
}
```

## Verification Commands

### Test SQS Permissions
```bash
# Test sending a message (should succeed)
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/908226940571/predictions-queue \
  --message-body '{"test": "message"}' \
  --region us-east-1

# Test receiving messages (should succeed)
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/908226940571/predictions-queue \
  --region us-east-1
```

### Verify IAM Policy Attachment
```bash
# List policies attached to the task role
aws iam list-attached-role-policies --role-name ACTUAL_ROLE_NAME

# Get policy document
aws iam get-policy-version \
  --policy-arn arn:aws:iam::908226940571:policy/retainwise-backend-sqs-send \
  --version-id v1
```

## Expected Outputs After Terraform Apply

```
predictions_queue_arn = "arn:aws:sqs:us-east-1:908226940571:predictions-queue"
predictions_queue_url = "https://sqs.us-east-1.amazonaws.com/908226940571/predictions-queue"
backend_sqs_policy_arn = "arn:aws:iam::908226940571:policy/retainwise-backend-sqs-send"
```

## Rollback Plan

If issues occur, detach the policy:
```bash
aws iam detach-role-policy \
  --role-name ACTUAL_ROLE_NAME \
  --policy-arn arn:aws:iam::908226940571:policy/retainwise-backend-sqs-send
```

Then delete the policy and queue via Terraform:
```bash
terraform destroy -target=aws_iam_role_policy_attachment.backend_sqs_send
terraform destroy -target=aws_iam_policy.backend_sqs_send
terraform destroy -target=aws_sqs_queue.predictions
``` 