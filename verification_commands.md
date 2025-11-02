# 🔍 **VERIFICATION COMMANDS**

## **Check Which Task Definition Worker is Using**

```bash
# Get current task definition for worker service
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-worker \
  --query 'services[0].taskDefinition' \
  --output text \
  --region us-east-1

# Expected: arn:aws:ecs:us-east-1:908226940571:task-definition/retainwise-worker:2 (or higher)

# List all task definition revisions
aws ecs list-task-definitions \
  --family-prefix retainwise-worker \
  --status ACTIVE \
  --region us-east-1

# Expected: Should show retainwise-worker:2 (or higher) as active
```

## **Check Worker Logs**

```bash
# Check startup logs
aws logs tail /ecs/retainwise-worker --follow --region us-east-1

# Look for this startup banner:
# ============================================================
# 🚀 Starting RetainWise Prediction Worker
# ============================================================
# Queue URL: ***/prod-retainwise-predictions-queue
# AWS Region: us-east-1
# Environment: production
# SQS Enabled: True
# ============================================================
# ✅ Worker ready - polling for messages...
```

## **Check Backend SQS Configuration**

```bash
# Get current backend task definition
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-service \
  --query 'services[0].taskDefinition' \
  --output text \
  --region us-east-1

# Get environment variables from task definition
aws ecs describe-task-definition \
  --task-definition retainwise-backend:76 \
  --query 'taskDefinition.containerDefinitions[0].environment' \
  --output json \
  --region us-east-1

# Look for:
# PREDICTIONS_QUEUE_URL: <queue-url>
# ENABLE_SQS: true
```

## **Check Database Migration**

```bash
# Connect to RDS and check columns
# (via EC2 jump host or port forward)

# Once connected:
psql> \d+ predictions

# Should show:
# sqs_message_id     | character varying(255) |
# sqs_queued_at      | timestamp with time zone |
```

## **Test End-to-End Prediction**

```bash
# Upload CSV via API
curl -X POST "https://api.retainwiseanalytics.com/api/csv" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@sample.csv" \
  -F "user_id=<clerk-id>"

# Watch worker logs
aws logs tail /ecs/retainwise-worker --follow --region us-east-1

# Should see:
# ✅ Processing prediction task (prediction_id=...)
# Prediction status updated to RUNNING
# ML prediction processing completed
# ✅ Message processed successfully
```

