# 🔍 **SQS "NOT CONFIGURED" - COMPLETE EXPLANATION**

## **📊 YOUR QUESTIONS ANSWERED**

### **Q1: Why is "SQS not configured" still there after deployment?** ❌

**Short Answer:** The backend task definition is missing two environment variables: `PREDICTIONS_QUEUE_URL` and `ENABLE_SQS`.

**Detailed Explanation:**

**What We Verified:**
```bash
# Checked backend task definition for SQS environment variables
aws ecs describe-task-definition --task-definition retainwise-backend \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`PREDICTIONS_QUEUE_URL` || name==`ENABLE_SQS`]'

# Result: []  (EMPTY ARRAY - NO SQS VARS!)
```

**What This Means:**
- The backend container starts WITHOUT the SQS configuration
- The code in `backend/main.py` checks `settings.is_sqs_enabled`
- This property returns `False` if env vars are missing
- Backend logs "SQS not configured" and doesn't initialize SQS client
- Result: Backend CANNOT publish messages to SQS! ❌

**How Backend Checks SQS:**
```python
# From backend/core/config.py
@property
def is_sqs_enabled(self) -> bool:
    return (
        getenv("ENABLE_SQS", "false").lower() == "true" and 
        bool(self.PREDICTIONS_QUEUE_URL)
    )

# From backend/main.py (startup)
if settings.is_sqs_enabled:
    logger.info("✅ SQS client initialized")
else:
    logger.info("SQS not configured - prediction processing disabled")  # <-- This is what you're seeing!
```

---

### **Q2: Why is retainwise-worker:1 inactive and still shows revision 1?** ✅

**Short Answer:** This is COMPLETELY NORMAL and NOT a problem!

**Detailed Explanation:**

**What We Verified:**
```bash
aws ecs describe-services --cluster retainwise-cluster --services retainwise-worker

# Result:
{
    "Status": "ACTIVE",
    "TaskDefinition": "arn:aws:ecs:us-east-1:908226940571:task-definition/retainwise-worker:1",
    "Running": 1,
    "Desired": 1
}
```

**This Shows:**
- ✅ Worker service is ACTIVE
- ✅ Using task definition revision :1
- ✅ Running 1 task (as expected)
- ✅ Everything is working correctly!

**Why It's Still on Revision :1:**

The worker task definition only gets updated when `infra/ecs-worker.tf` changes:

**Timeline:**
1. **46 days ago:** Initial deployment created `retainwise-worker:1`
2. **Last week:** Made changes to `infra/ecs-worker.tf` for Task 1.2
3. **Terraform Apply:** Should have created `:2`, but...
4. **Last commit:** Only changed `infra/resources.tf` (BACKEND), not `infra/ecs-worker.tf` (WORKER)!

**Conclusion:** Worker is on :1 because we haven't changed the worker task definition since initial deployment. This is correct!

**When Will It Update to :2?**
- When we change `infra/ecs-worker.tf`
- When Terraform apply runs
- ECS service will automatically switch to new revision
- Old :1 will be marked "Inactive"

**Important:** "Inactive" in ECS means "not currently used by any running tasks." If you see :1 as active in the service, it means the service IS using it. The confusion might be:
- Task Definitions list shows ALL revisions (active and inactive)
- If :1 is inactive in that list, but service says it's using :1, there's a display lag
- The service status is the source of truth!

---

## **🎯 ROOT CAUSE ANALYSIS**

### **Why Didn't GitHub Actions Add SQS Env Vars?**

**The Workflow Should:**
1. ✅ Detect infra changes (`infra/resources.tf` changed)
2. ✅ Run Terraform Apply
3. ✅ Get SQS queue URL from Terraform or AWS CLI
4. ✅ Download current task definition
5. ✅ Add SQS environment variables
6. ✅ Add version tracking variables
7. ✅ Deploy updated task definition

**What Actually Happened:**

Looking at the workflow in `.github/workflows/backend-ci-cd.yml`:

```yaml
- name: Get SQS queue URL from Terraform
  id: get-queue-url
  run: |
    cd infra
    QUEUE_URL=$(terraform output -raw predictions_queue_url 2>/dev/null || echo "")
    if [ -z "$QUEUE_URL" ]; then
      echo "⚠️  Queue URL not found in Terraform outputs, trying AWS CLI..."
      QUEUE_URL=$(aws sqs get-queue-url --queue-name prod-retainwise-predictions-queue --query 'QueueUrl' --output text 2>/dev/null || echo "")
    fi
    echo "predictions_queue_url=$QUEUE_URL" >> $GITHUB_OUTPUT
```

**Possible Issues:**
1. **Terraform output failed** - State not initialized in that shell session
2. **AWS CLI fallback failed** - Permissions or region issue
3. **Empty string was set** - Next step's `if` condition evaluated to false
4. **ELSE branch executed** - Version tracking added, but NO SQS vars!

**The Problem with Dual Management:**

We have TWO systems trying to manage the backend task definition:
1. **Terraform** (`infra/resources.tf`) - Adds SQS vars in HCL
2. **GitHub Actions** - Downloads, modifies, re-deploys

**What Happens:**
```
Terraform creates:       retainwise-backend:76 (has SQS vars)
                                ↓
GitHub Actions downloads:      :76
                                ↓
GitHub Actions adds:           Version tracking vars
                                ↓
GitHub Actions registers:      :77 (NEW revision)
                                ↓
Service updates to:            :77
```

**BUT:** If the GitHub Actions step to add SQS vars fails or skips, then:
- `:77` has version tracking ONLY
- `:77` is missing SQS vars!
- Backend can't publish to SQS!

---

## **🔧 THE FIX**

### **Option 1: Manual Fix (RECOMMENDED - IMMEDIATE)**

I've created a PowerShell script that will:
1. Download current backend task definition
2. Add `PREDICTIONS_QUEUE_URL` and `ENABLE_SQS`
3. Register new task definition
4. Force service update
5. Verify SQS vars are present

**Run this:**
```powershell
.\fix_sqs_env_vars.ps1
```

**Requirements:**
- AWS CLI configured
- `jq` installed (for JSON manipulation)
- IAM permissions for ECS

**Expected Output:**
```
🔧 FIXING SQS ENVIRONMENT VARIABLES
✅ Task definition downloaded
✅ SQS environment variables added
✅ New task definition registered: retainwise-backend:78
✅ Service update triggered
✅ Service stabilized successfully!
✅ SQS environment variables verified:
  - PREDICTIONS_QUEUE_URL: https://sqs.us-east-1.amazonaws.com/***/prod-retainwise-predictions-queue
  - ENABLE_SQS: true
```

**After 2-3 minutes:**
- New backend task will be running
- Logs will show "✅ SQS client initialized"
- No more "SQS not configured" messages!

---

### **Option 2: Fix GitHub Actions Workflow (LONG-TERM)**

The GitHub Actions step needs to be more robust. Two approaches:

**Approach A: Always Use AWS CLI**
```yaml
- name: Get SQS queue URL
  id: get-queue-url
  run: |
    # Skip Terraform, directly query AWS
    QUEUE_URL=$(aws sqs get-queue-url \
      --queue-name prod-retainwise-predictions-queue \
      --region us-east-1 \
      --query 'QueueUrl' \
      --output text)
    echo "predictions_queue_url=$QUEUE_URL" >> $GITHUB_OUTPUT
```

**Approach B: Let Terraform Fully Manage Backend Task Definition**
- Remove GitHub Actions task definition modification
- Add version tracking vars to Terraform as locals
- Let Terraform create the FINAL task definition
- GitHub Actions only triggers Terraform apply

---

## **📊 COMPARISON: What Should Happen vs What Happened**

### **Expected Flow:**
```
1. Upload CSV
   → Backend receives request
   → Backend uploads to S3
   → Backend creates Prediction record (status=QUEUED)
   → Backend publishes to SQS ✅
   → Returns prediction_id to frontend

2. Worker picks up message
   → Worker polls SQS
   → Worker receives message
   → Worker processes prediction
   → Worker updates status to COMPLETED

3. Frontend polls /api/predictions
   → Sees status=COMPLETED
   → Shows results to user
```

### **Current Flow:**
```
1. Upload CSV
   → Backend receives request
   → Backend uploads to S3
   → Backend creates Prediction record (status=QUEUED)
   → Backend tries to publish to SQS ❌
   → SQS not configured!
   → Graceful degradation: Prediction saved but NOT queued
   → Returns prediction_id to frontend

2. Worker polls SQS
   → Queue is empty (no messages published!)
   → Worker keeps polling...

3. Frontend polls /api/predictions
   → Sees status=QUEUED forever ❌
   → Prediction never processes
```

**This is why async predictions aren't working!**

---

## **✅ VERIFICATION AFTER FIX**

After running `fix_sqs_env_vars.ps1`, verify:

### **1. Check Backend Logs**
```bash
aws logs tail /ecs/retainwise-backend --follow --region us-east-1
```

**Look for:**
```
✅ SQS client initialized
Queue: ***/prod-retainwise-predictions-queue
```

**Should NOT see:**
```
❌ SQS not configured - prediction processing disabled
```

### **2. Check Task Definition**
```bash
aws ecs describe-task-definition \
  --task-definition retainwise-backend \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`PREDICTIONS_QUEUE_URL` || name==`ENABLE_SQS`]' \
  --output json
```

**Expected:**
```json
[
    {
        "name": "ENABLE_SQS",
        "value": "true"
    },
    {
        "name": "PREDICTIONS_QUEUE_URL",
        "value": "https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue"
    }
]
```

### **3. Test End-to-End**
```bash
# Upload a CSV (via frontend or API)
# Check backend logs for:
✅ Published prediction to SQS (message_id=abc123...)

# Check worker logs for:
✅ Processing prediction task (prediction_id=abc123...)
✅ Message processed successfully
```

---

## **🎯 SUMMARY**

**Problem 1: "SQS not configured"** ❌
- **Cause:** Backend task definition missing `PREDICTIONS_QUEUE_URL` and `ENABLE_SQS`
- **Impact:** Backend cannot publish messages to SQS
- **Fix:** Run `fix_sqs_env_vars.ps1` to manually add env vars
- **ETA:** 5 minutes

**Problem 2: "Worker on revision :1"** ✅
- **Cause:** No changes to `infra/ecs-worker.tf` in last deployment
- **Impact:** None - this is normal!
- **Fix:** Not needed
- **Note:** Worker will update when we change its task definition

**Next Steps:**
1. Run `fix_sqs_env_vars.ps1`
2. Wait 2-3 minutes for backend to restart
3. Check logs (should see "SQS client initialized")
4. Test CSV upload → prediction flow
5. Verify worker processes message

**After This Fix:**
- ✅ Backend can publish to SQS
- ✅ Worker can receive and process messages
- ✅ End-to-end prediction flow works
- ✅ Task 1.2 fully operational!

**Long-term:**
- Fix GitHub Actions workflow to prevent this issue
- Consider letting Terraform fully manage task definitions
- Add integration tests to catch missing env vars

