# 🚀 **TASK 1.2 DEPLOYMENT GUIDE**

## **Quick Deployment Steps**

This guide gets Task 1.2 deployed to production in **~15 minutes**.

---

## **✅ PRE-DEPLOYMENT CHECKLIST**

- [x] Task 1.1 complete (SQS queues deployed)
- [x] Task 1.2 code complete (worker service ready)
- [x] Database migration created
- [x] Infrastructure files updated
- [ ] Database migration run
- [ ] Docker image built and pushed
- [ ] Worker service deployed

---

## **🚀 DEPLOYMENT (3 Steps)**

### **Step 1: Run Database Migration** (2 minutes)

```bash
# Connect to production RDS
# Option A: Via EC2 jump host
ssh ec2-user@<jump-host-ip>
psql -h retainwise-db.xxxxx.us-east-1.rds.amazonaws.com -U retainwise_user -d retainwise

# Option B: Via local tunnel
aws ssm start-session --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters "portNumber=5432,localPortNumber=5432"

psql -h localhost -U retainwise_user -d retainwise
```

```sql
-- Run migration manually (if alembic not available on RDS)
-- Add SQS metadata columns
ALTER TABLE predictions 
ADD COLUMN IF NOT EXISTS sqs_message_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS sqs_queued_at TIMESTAMP WITH TIME ZONE;

-- Verify columns
\d+ predictions

-- Expected output includes:
-- sqs_message_id  | character varying(255) | 
-- sqs_queued_at   | timestamp with time zone |
```

---

### **Step 2: Deploy via GitHub Actions** (10 minutes)

```bash
# Commit all changes
git add backend/ infra/ *.md
git commit -m "feat: Add production-grade worker service (Task 1.2)

- Fix field mapping mismatch (s3_file_path vs s3_key)
- Add missing SQS metadata columns to Prediction model
- Create Alembic migration for new columns
- Enhance worker with Pydantic validation
- Add comprehensive logging and metrics
- Add graceful shutdown handling
- Update ECS worker infrastructure
- Fix task role reference in Terraform

Task 1.2 complete. Worker ready for deployment.
"

# Push to main (triggers GitHub Actions)
git push origin main
```

**GitHub Actions will:**
1. ✅ Build Docker image with worker code
2. ✅ Push to ECR
3. ✅ Update ECS task definitions (backend + worker)
4. ✅ Deploy to ECS

**Monitor deployment:**
```bash
# Watch GitHub Actions
# https://github.com/muhammadzeb86/churn-saas/actions

# Expected: ✅ Build and Deploy to AWS completed
```

---

### **Step 3: Verify Deployment** (3 minutes)

```bash
# Check worker service status
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-worker \
  --region us-east-1 \
  --query 'services[0].{Status:status,Desired:desiredCount,Running:runningCount}'

# Expected:
# {
#   "Status": "ACTIVE",
#   "Desired": 1,
#   "Running": 1
# }

# Check logs
aws logs tail /ecs/retainwise-worker --follow --region us-east-1

# Expected output:
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

---

## **🧪 POST-DEPLOYMENT TESTING**

### **Test 1: Upload CSV**

```bash
# Via frontend (easiest)
# 1. Login to https://retainwiseanalytics.com
# 2. Upload sample.csv
# 3. Wait 2-5 minutes
# 4. Check predictions page

# Via API (for testing)
curl -X POST "https://backend.retainwiseanalytics.com/api/csv" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@sample.csv" \
  -F "user_id=<your-clerk-id>"

# Expected response:
# {
#   "success": true,
#   "prediction_id": "abc123...",
#   "status": "queued",
#   "message": "Prediction queued for processing (estimated 2-5 minutes)"
# }
```

### **Test 2: Monitor Processing**

```bash
# Watch worker logs
aws logs tail /ecs/retainwise-worker --follow --region us-east-1

# Expected flow:
# ✅ Processing prediction task (prediction_id=abc123...)
# Prediction status updated to RUNNING
# ML prediction processing completed
# Prediction processing completed successfully
# ✅ Message processed successfully (total_processed=1)
```

### **Test 3: Verify Completion**

```bash
# Check prediction status
curl "https://backend.retainwiseanalytics.com/api/predictions/abc123..." \
  -H "Authorization: Bearer <JWT_TOKEN>"

# Expected:
# {
#   "id": "abc123...",
#   "status": "COMPLETED",
#   "rows_processed": 1000,
#   "s3_output_key": "predictions/user_xxx/abc123....csv",
#   "created_at": "2025-11-02T...",
#   "updated_at": "2025-11-02T..."
# }
```

---

## **🚨 TROUBLESHOOTING**

### **Migration Failed**

```bash
# Check if columns already exist
psql -h <rds-endpoint> -U retainwise_user -d retainwise -c "\d+ predictions"

# If columns exist, migration succeeded (idempotent)
# If not, re-run ALTER TABLE commands above
```

### **Worker Not Starting**

```bash
# Check service events
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-worker \
  --region us-east-1 \
  --query 'services[0].events[0:5]'

# Common issues:
# - "unable to pull image" → Docker image not pushed to ECR
# - "Task failed to start" → Check IAM permissions
# - "Service is unhealthy" → Check logs for startup errors
```

### **No Messages Processing**

```bash
# Check queue has messages
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue \
  --attribute-names ApproximateNumberOfMessages \
  --region us-east-1

# Check worker has SQS permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::908226940571:role/prod-retainwise-worker-task-role \
  --action-names sqs:ReceiveMessage sqs:DeleteMessage \
  --resource-arns arn:aws:sqs:us-east-1:908226940571:prod-retainwise-predictions-queue

# Expected: "allowed" for both actions
```

---

## **📊 MONITORING**

### **Key CloudWatch Log Queries**

```sql
-- Success rate
fields @timestamp, event, total_processed, total_failed
| filter event = "message_processed" or event = "message_processing_failed"
| stats latest(total_processed) as processed, latest(total_failed) as failed

-- Processing time
fields @timestamp, prediction_id, @message
| filter event = "prediction_processing_started" or event = "prediction_processing_completed"
| stats count() by bin(5m)

-- Errors
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /❌/
| sort @timestamp desc
```

### **CloudWatch Alarms**

Check alarm status:
```bash
aws cloudwatch describe-alarms \
  --alarm-names prod-predictions-dlq-messages prod-predictions-queue-age \
  --region us-east-1
```

Both should show `"StateValue": "OK"`

---

## **✅ SUCCESS CRITERIA**

All must be ✅ before considering deployment successful:

- [ ] Database migration completed (columns exist)
- [ ] Worker service running (1 task)
- [ ] Worker logs show startup banner
- [ ] Worker polling SQS queue
- [ ] Test prediction completes end-to-end
- [ ] No errors in CloudWatch logs
- [ ] CloudWatch alarms in "OK" state
- [ ] No messages in DLQ

---

## **🎯 ROLLBACK PLAN** (if needed)

```bash
# Option 1: Disable worker (fastest)
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --desired-count 0 \
  --region us-east-1

# Option 2: Revert to previous task definition
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --task-definition retainwise-worker:<previous-revision> \
  --force-new-deployment \
  --region us-east-1

# Option 3: Disable SQS publishing (backend only)
# Set ENABLE_SQS=false in backend ECS task definition
# Predictions will stay QUEUED until worker re-enabled
```

---

## **📞 NEXT STEPS AFTER DEPLOYMENT**

1. ✅ Monitor for 30 minutes
2. ✅ Test with 5-10 sample predictions
3. ✅ Check cost metrics (should be ~$17/month)
4. ✅ Update status to "DEPLOYED" in master plan
5. ➡️ Begin Task 1.3: End-to-End Testing

---

## **📚 REFERENCES**

- **Task 1.2 Summary:** `TASK_1.2_COMPLETE_SUMMARY.md`
- **Task 1.1 Summary:** `TASK_1.1_COMPLETE_SUMMARY.md`
- **Master Plan:** `ML_IMPLEMENTATION_MASTER_PLAN.md`
- **AWS ECS Docs:** https://docs.aws.amazon.com/ecs/
- **AWS SQS Docs:** https://docs.aws.amazon.com/sqs/

---

**Good luck with deployment! 🚀**

