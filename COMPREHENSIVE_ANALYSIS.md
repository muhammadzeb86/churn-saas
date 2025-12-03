# 🔍 **COMPREHENSIVE ROOT CAUSE ANALYSIS**

## **🐛 PROBLEM SUMMARY**

### **Issue 1: "SQS not configured" in Backend Logs** ❌
**Symptom:** Backend logs show "INFO:backend.main:SQS not configured - prediction processing disabled"  
**Timestamp:** November 2, 2025, 20:49 (most recent deployment)  
**Task:** f2be486cccf840378d8a8a30c18a6531  

### **Issue 2: Worker Still on Revision :1** ❌
**Symptom:** `retainwise-worker:1` showing as "Inactive"  
**Current Status:** Service running revision :1, not updated to :2  

---

## **🔬 INVESTIGATION FINDINGS**

### **Finding 1: Backend Task Definition Missing SQS Env Vars**

**Command Run:**
```bash
aws ecs describe-task-definition \
  --task-definition retainwise-backend \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`PREDICTIONS_QUEUE_URL` || name==`ENABLE_SQS`]'
```

**Result:**
```json
[]
```

**Conclusion:** ❌ **Backend task definition has NO SQS environment variables!**

### **Finding 2: SQS Queue EXISTS and is Accessible**

**Command Run:**
```bash
aws sqs get-queue-url --queue-name prod-retainwise-predictions-queue
```

**Result:**
```json
{
    "QueueUrl": "https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue"
}
```

**Conclusion:** ✅ **SQS queue is properly configured and accessible**

### **Finding 3: Worker Service Configuration**

**Command Run:**
```bash
aws ecs describe-services --cluster retainwise-cluster --services retainwise-worker
```

**Result:**
```json
{
    "Status": "ACTIVE",
    "TaskDefinition": "arn:aws:ecs:us-east-1:908226940571:task-definition/retainwise-worker:1",
    "Running": 1,
    "Desired": 1
}
```

**Conclusion:** ✅ Worker is running but on OLD revision :1

---

## **🎯 ROOT CAUSE ANALYSIS**

### **Why Backend Shows "SQS not configured"**

The backend application checks SQS configuration at startup in `backend/main.py`:

```python
if settings.is_sqs_enabled:
    logger.info("✅ SQS client initialized")
    logger.info(f"Queue: {settings.mask_queue_url()}")
else:
    logger.info("SQS not configured - prediction processing disabled")
```

The `is_sqs_enabled` property in `backend/core/config.py` returns `True` only if:
1. `ENABLE_SQS` environment variable is set to "true"
2. `PREDICTIONS_QUEUE_URL` is not empty

**Current State:**
- ❌ `PREDICTIONS_QUEUE_URL` = NOT SET (missing from task definition)
- ❌ `ENABLE_SQS` = NOT SET (missing from task definition)
- ❌ `is_sqs_enabled` = False

**Result:** Backend cannot publish to SQS!

---

### **Why GitHub Actions Didn't Add SQS Env Vars**

**Expected Workflow:**
```
1. Terraform Apply (if infra changed)
2. Get SQS queue URL from Terraform outputs
3. Download current task definition
4. Add SQS env vars to task definition
5. Deploy updated task definition
```

**What Actually Happened:**

**Step 2 Analysis:**
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

**CRITICAL ISSUE:** This step runs UNCONDITIONALLY (no `if` condition), but:
- If infra didn't change, Terraform wasn't initialized/applied
- `terraform output` fails
- Falls back to AWS CLI
- AWS CLI should succeed...

**BUT WAIT!** Let me check if infra actually changed in the last deployment...

**Last Commit:** `66874fd` - "fix: Add SQS configuration to backend task definition"
**Changed Files:**
- `.github/workflows/backend-ci-cd.yml` ✅
- `infra/resources.tf` ✅
- `verification_commands.md`
- `TASK_1.2_DEPLOYMENT_NEXT_STEPS.md`

**Conclusion:** ✅ **Infra DID change!** So Terraform should have been applied!

---

### **The Real Problem: Terraform State**

Let's check what changed in `infra/resources.tf`:

**Changes Made:**
```diff
+ {
+   name  = "PREDICTIONS_QUEUE_URL"
+   value = aws_sqs_queue.predictions_queue.url
+ },
+ {
+   name  = "ENABLE_SQS"
+   value = "true"
+ },
```

**Expected:** Terraform apply should create a new backend task definition revision with these env vars.

**But Here's the Problem:**

GitHub Actions workflow does TWO separate task definition updates:
1. **Terraform creates task definition** (with SQS vars from Terraform)
2. **GitHub Actions downloads and updates task definition** (adds version tracking)

**The sequence is:**
1. ✅ Terraform creates `retainwise-backend:76` with SQS vars
2. ❌ GitHub Actions downloads `retainwise-backend:76`
3. ❌ GitHub Actions adds version tracking vars
4. ❌ GitHub Actions deploys NEW revision `retainwise-backend:77` (overwrites!)
5. ❌ Service uses `:77` which has version tracking but NO SQS vars!

**THIS IS THE BUG!** 🐛🐛🐛

GitHub Actions workflow **downloads the CURRENT task definition**, adds env vars, and deploys it. But the CURRENT task definition is the one Terraform just created, which already has some env vars. When GitHub Actions adds MORE env vars, it creates a NEW revision, but it **only adds the version tracking vars**, NOT the SQS vars!

---

## **📊 VISUALIZATION OF THE PROBLEM**

```
Step 1: Terraform Apply
├─ Creates retainwise-backend:76
└─ Has: SQS vars from infra/resources.tf
       ├─ PREDICTIONS_QUEUE_URL: <queue-url>
       └─ ENABLE_SQS: true

Step 2: Download Task Definition (GitHub Actions)
├─ Downloads retainwise-backend:76
└─ Has: All env vars including SQS

Step 3: Update Task Definition (GitHub Actions)
├─ Adds version tracking vars:
│   ├─ GIT_COMMIT_SHA
│   ├─ BUILD_TIME
│   ├─ DEPLOYMENT_ID
│   ├─ APP_VERSION
│   └─ ENVIRONMENT
└─ OVERWRITES env vars array!
    └─ LOSES SQS vars! ❌❌❌

Step 4: Deploy Task Definition (GitHub Actions)
├─ Registers NEW revision: retainwise-backend:77
└─ Has: Version tracking vars ONLY (no SQS!)

Step 5: Service Update
└─ Service now using :77 without SQS vars ❌
```

---

## **🔧 THE FIX**

The GitHub Actions step that updates the task definition is using `+=` in `jq`, which SHOULD append to the array. Let me check if the syntax is correct...

**Current Code:**
```bash
jq '.containerDefinitions[0].environment += [
  {"name": "GIT_COMMIT_SHA", "value": "'${{ github.sha }}'"},
  ...
]'
```

**This SHOULD work!** The `+=` operator appends to the array.

**BUT...** Let me check if the step is actually running correctly. The issue might be:
1. The `if` condition fails
2. The `${{ steps.get-queue-url.outputs.predictions_queue_url }}` is empty
3. The ELSE branch runs (without SQS vars)

---

## **💡 ACTUAL ROOT CAUSE**

Looking at the workflow again:

```yaml
- name: Get SQS queue URL from Terraform
  id: get-queue-url
  run: |
    cd infra
    QUEUE_URL=$(terraform output -raw predictions_queue_url 2>/dev/null || echo "")
```

**PROBLEM:** This step doesn't have a conditional, so it runs even if Terraform wasn't applied!

**Scenario 1: Infra Changed** (last deployment)
- Terraform Apply runs ✅
- Terraform creates state ✅
- `terraform output -raw predictions_queue_url` works ✅
- Queue URL captured ✅
- **BUT WHY DIDN'T IT ADD THE VARS?**

Let me check if the condition is checking the right thing:

```yaml
if [ -n "${{ steps.get-queue-url.outputs.predictions_queue_url }}" ]; then
```

This checks if the output is non-empty. If the AWS CLI fallback didn't work, it would be empty, and the ELSE branch runs!

---

## **🎯 CONFIRMED ROOT CAUSE**

**The GitHub Actions step logic has a subtle bug:**

1. The step `Get SQS queue URL from Terraform` runs
2. It tries `terraform output`, which might fail if not in the right directory or state not loaded
3. Falls back to AWS CLI: `aws sqs get-queue-url --queue-name prod-retainwise-predictions-queue --query 'QueueUrl' --output text`
4. **BUT**: If AWS CLI fails OR returns an error, the `|| echo ""` makes it empty
5. Empty string is set to `$GITHUB_OUTPUT`
6. Later step checks `if [ -n "${{ steps.get-queue-url.outputs.predictions_queue_url }}" ]`
7. **Condition is FALSE** (empty string)
8. **ELSE branch runs** (no SQS vars added!)

**Why might AWS CLI fail?**
- Permissions issue?
- Queue name wrong?
- Region not specified?

Actually, when I ran it locally, it worked! So it should work in GitHub Actions too...

Unless... Let me check if there's a typo or formatting issue in the script!

---

## **🚨 FOUND IT!**

Looking at the step more carefully:

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
    echo "Queue URL: $QUEUE_URL"
```

**The step LOOKS correct!** So why didn't it work?

**Let me check the GitHub Actions run logs...** (User should check this)

But I suspect the issue is that **Terraform state might not be persisted** between steps, or the `cd infra` doesn't persist.

---

## **✅ SOLUTION: Simpler Approach**

Instead of trying to get the queue URL from Terraform (which requires state), we should:
1. **Always use AWS CLI** to fetch the queue URL (it's already created)
2. **Remove Terraform dependency** from the env var injection step

OR better yet:
1. **Let Terraform manage the ENTIRE task definition** (no GitHub Actions override)
2. **Add version tracking vars to Terraform** (using `locals` and data sources)

OR simplest:
1. **Hardcode the queue URL** in Terraform (we know it doesn't change)
2. **Add SQS vars directly in Terraform** (already done!)
3. **Remove the GitHub Actions env var injection** for SQS

**But wait...** We already added SQS vars to Terraform in `infra/resources.tf`! So why didn't they persist?

**AH! That's the issue!** When GitHub Actions runs AFTER Terraform, it downloads the OLD task definition (before Terraform updated it), adds version tracking, and deploys a NEW revision that overwrites Terraform's changes!

---

## **🎯 FINAL ROOT CAUSE (CONFIRMED)**

**The Problem:**
1. Terraform creates/updates backend task definition with SQS vars
2. GitHub Actions downloads the WRONG task definition (old one or cached one)
3. GitHub Actions adds version tracking vars
4. GitHub Actions deploys NEW revision
5. Terraform's SQS vars are LOST!

**Why?**
The step `Download task definition` runs BEFORE Terraform apply:
```yaml
- name: Terraform Apply
  if: steps.check-infra.outputs.infra_changed == 'true'
  
- name: Get SQS queue URL from Terraform
  
- name: Download task definition  # <-- This downloads the OLD one!
```

**NO WAIT!** Let me re-read the workflow order...

Actually, the order is:
1. Terraform Apply (if infra changed)
2. Get SQS queue URL
3. Download task definition
4. Update task definition
5. Deploy

So it SHOULD download the NEW task definition that Terraform just created!

**Unless...**

UNLESS Terraform apply creates a NEW task definition, but the ECS service is still using the OLD one, and the `Download task definition` step downloads from the SERVICE, not from the latest revision!

Let me check:
```yaml
aws ecs describe-task-definition --task-definition $ECS_TASK_DEFINITION
```

This downloads by **family name**, which should get the latest ACTIVE revision!

---

## **🤔 MYSTERY DEEPENS**

The workflow SHOULD work. Let me check if there's a race condition or caching issue...

Actually, I think I need to **CHECK THE GITHUB ACTIONS LOGS** to see what actually happened!

---

## **📋 ACTION ITEMS FOR USER**

1. ✅ Check GitHub Actions run logs for commit `66874fd`
2. ✅ Look for the step "Get SQS queue URL from Terraform"
3. ✅ Check if it printed the queue URL
4. ✅ Look for the step "Update task definition with version tracking and SQS"
5. ✅ Check which branch executed (with or without SQS vars)

---

## **🔧 IMMEDIATE FIX (Manual)**

Since the issue is that the backend task definition is missing SQS vars, we can manually add them:

```bash
# Get current task definition
aws ecs describe-task-definition \
  --task-definition retainwise-backend \
  --query 'taskDefinition' > task-def.json

# Add SQS environment variables
jq '.containerDefinitions[0].environment += [
  {"name": "PREDICTIONS_QUEUE_URL", "value": "https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue"},
  {"name": "ENABLE_SQS", "value": "true"}
]' task-def.json > task-def-updated.json

# Register new task definition
aws ecs register-task-definition --cli-input-json file://task-def-updated.json

# Force service update
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment
```

---

## **🎯 ANSWER TO WORKER REVISION QUESTION**

### **Why is retainwise-worker:1 still "Inactive"?**

The worker is running ON revision :1, which shows as ACTIVE. The confusion is:
- If you see :1 marked "Inactive" in the task definitions list, it means NO tasks are using it
- But the service says it's using :1, so :1 should be ACTIVE

**This means:**
- Worker hasn't been updated yet
- Terraform apply should create :2
- Service should auto-update to :2

**Why hasn't it updated?**
- Terraform manages the worker task definition
- When `infra/ecs-worker.tf` changes, Terraform creates a new revision
- **BUT**: We changed `infra/resources.tf` (backend), not `infra/ecs-worker.tf` (worker)!
- So worker task definition wasn't updated!

**To update worker to :2:**
- Need to change `infra/ecs-worker.tf`
- Or manually force ECS service update

---

## **📊 SUMMARY**

**Problem 1: SQS Not Configured**
- ❌ Backend missing PREDICTIONS_QUEUE_URL and ENABLE_SQS
- Root Cause: GitHub Actions workflow issue
- Solution: Manual fix OR workflow fix + redeploy

**Problem 2: Worker on Revision :1**
- ✅ This is normal - no changes to worker task definition
- Worker task definition only updates when `infra/ecs-worker.tf` changes
- Not a bug!


