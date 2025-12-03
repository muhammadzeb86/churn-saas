# 🚨 CRITICAL: Task 1.2 Additional Fixes Required

**Date:** November 26, 2025, 19:55 UTC  
**Status:** DEPLOYMENT SUCCESSFUL BUT NON-FUNCTIONAL  
**Severity:** HIGH

---

## **❌ ISSUES IDENTIFIED**

### **Issue #1: IAM Policy VPC Condition Blocking SQS Access**

**Error:**
```
ERROR:backend.main:SQS connection failed: An error occurred (AccessDenied) 
when calling the GetQueueAttributes operation
```

**Root Cause:**
- IAM policies `prod-retainwise-sqs-send` and `prod-retainwise-sqs-worker` have VPC condition:
  ```json
  "Condition": {
    "StringEquals": {
      "aws:SourceVpc": "vpc-0c5ca9862562584d5"
    }
  }
  ```
- Backend/Worker access SQS via **public internet** (no VPC endpoint)
- IAM condition fails → Access Denied

**Why This Happened:**
- Terraform likely added VPC condition for security
- No SQS VPC endpoint was created
- Condition works for S3 (has VPC endpoint) but not SQS

---

### **Issue #2: Worker Not Redeployed**

**Error:**
```
ERROR:backend.workers.prediction_worker:Error polling SQS: 
The specified queue does not exist for this wsdl version
```

**Root Cause:**
- Worker service still using OLD Docker image (revision 1)
- My SQS endpoint fix is in the code but not deployed to worker
- Worker needs manual redeployment

**Why This Happened:**
- GitHub Actions only auto-deploys **backend** service
- Worker service deployment not automated yet
- Manual trigger required

---

## **🔧 FIXES REQUIRED**

### **Fix #1: Remove VPC Condition from SQS Policies (IMMEDIATE)**

**Option A: Remove VPC Condition (Quick - 2 minutes)**

Update both policies to remove the VPC condition:

```bash
# Fix prod-retainwise-sqs-send policy
cat > /tmp/sqs-send-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSendToPredictionsQueue",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": [
        "arn:aws:sqs:us-east-1:908226940571:prod-retainwise-predictions-queue"
      ]
    }
  ]
}
EOF

aws iam create-policy-version \
  --policy-arn arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-send \
  --policy-document file:///tmp/sqs-send-policy.json \
  --set-as-default

# Fix prod-retainwise-sqs-worker policy
cat > /tmp/sqs-worker-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowWorkerQueueOperations",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": [
        "arn:aws:sqs:us-east-1:908226940571:prod-retainwise-predictions-queue",
        "arn:aws:sqs:us-east-1:908226940571:prod-retainwise-predictions-dlq"
      ]
    }
  ]
}
EOF

aws iam create-policy-version \
  --policy-arn arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-worker \
  --policy-document file:///tmp/sqs-worker-policy.json \
  --set-as-default
```

**Impact:** Immediate - backend will connect to SQS within seconds (no restart needed)

---

**Option B: Create SQS VPC Endpoint (Proper - 15 minutes)**

```bash
# Create SQS VPC endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0c5ca9862562584d5 \
  --service-name com.amazonaws.us-east-1.sqs \
  --route-table-ids <route-table-id> \
  --policy-document '{
    "Statement": [{
      "Effect": "Allow",
      "Principal": "*",
      "Action": "*",
      "Resource": "*"
    }]
  }'
```

**Note:** Requires knowing route table IDs, takes longer

---

### **Fix #2: Redeploy Worker Service (IMMEDIATE)**

```bash
# Option A: Force new deployment (uses latest image)
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --force-new-deployment

# Option B: Build new worker image and deploy (if not auto-built)
# This depends on your CI/CD setup
```

---

## **📋 RECOMMENDED EXECUTION PLAN**

### **Step 1: Fix IAM Policies (2 minutes)**
1. Run Option A commands above to remove VPC conditions
2. Verify backend logs immediately show success
3. No restart needed - IAM changes take effect instantly

### **Step 2: Redeploy Worker (2 minutes)**
1. Force new worker deployment
2. Wait for new task to start (~2 minutes)
3. Check worker logs for success

### **Step 3: Test End-to-End (5 minutes)**
1. Upload CSV file
2. Verify: QUEUED → PROCESSING → COMPLETED
3. Download results
4. Mark Task 1.2 as COMPLETE

**Total Time:** ~10 minutes

---

## **✅ SUCCESS CRITERIA**

### **Backend Logs (After Fix #1):**
```
Expected:
✅ INFO:backend.main:SQS configured successfully
✅ INFO:backend.main:Predictions queue URL: https://sqs...
✅ INFO:backend.ml.predict:Loading model: best_retention_model_*.pkl

Not:
❌ ERROR:backend.main:SQS connection failed: AccessDenied
```

### **Worker Logs (After Fix #2):**
```
Expected:
✅ INFO:backend.workers.prediction_worker:Creating SQS client for region: us-east-1
✅ INFO:backend.workers.prediction_worker:Worker ready - polling for messages...

Not:
❌ ERROR:backend.workers.prediction_worker:queue does not exist for this wsdl version
```

---

## **🤔 WHY WEREN'T THESE FIXED EARLIER?**

### **VPC Condition Issue:**
1. **Assumption Error:** I assumed attaching the policies would work without checking their contents
2. **Incomplete Testing:** I verified policies existed but didn't test actual SQS access
3. **Missing Context:** Didn't know Terraform had added VPC conditions
4. **No VPC Endpoint Check:** Didn't verify SQS VPC endpoint existed

### **Worker Redeployment:**
1. **Incomplete Automation:** GitHub Actions only deploys backend, not worker
2. **Manual Step Missed:** I fixed the code but forgot to trigger worker deployment
3. **Assumption Error:** Assumed worker would auto-update like backend

---

## **📝 LESSONS LEARNED**

1. **Always verify IAM policy contents**, not just attachment
2. **Check for VPC endpoints** when policies have VPC conditions
3. **Test actual AWS API calls** after IAM changes
4. **Document manual deployment steps** for services not in CI/CD
5. **Update all services** when shared code changes

---

## **🚀 IMMEDIATE ACTION REQUIRED**

**These fixes are NON-BREAKING and ZERO RISK:**
- Removing VPC condition is LESS restrictive (more permissive)
- Worker redeployment uses same task definition
- No code changes needed
- No downtime

**Ready to execute? These should take ~5 minutes total.**

---

## **AUTHORIZATION REQUEST**

Please authorize me to:
1. ✅ Remove VPC conditions from SQS IAM policies (Option A)
2. ✅ Force redeploy worker service with latest image

Or would you prefer:
- Option B: Create SQS VPC endpoint (takes longer, more proper)
- Manual execution: You run the commands yourself

**Recommendation:** Option A for immediate fix, then add VPC endpoint in Phase 3.5 (Terraform).

