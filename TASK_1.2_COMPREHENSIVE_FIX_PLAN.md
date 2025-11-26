# 🎯 Task 1.2 Comprehensive Fix Plan - Option B

**Date:** November 11, 2025, 21:52 UTC  
**Status:** IN PROGRESS - Executing Production-Grade Fix

---

## **🔍 ROOT CAUSE ANALYSIS**

### **Issue Summary:**
- ✅ SQS queues exist and are properly configured
- ✅ Worker service is running
- ✅ IAM roles with proper permissions exist
- ❌ **Task definitions are using WRONG IAM roles**

### **Detailed Findings:**

**Current State:**
```
Worker Task Definition:
  task_role_arn: retainwise-ecs-task-role (OLD - no SQS permissions)
  
Backend Task Definition:
  task_role_arn: retainwise-ecs-task-role (OLD - limited SQS permissions)
```

**Desired State:**
```
Worker Task Definition:
  task_role_arn: prod-retainwise-worker-task-role (NEW - has SQS receive/delete)
  
Backend Task Definition:
  task_role_arn: prod-retainwise-backend-task-role (NEW - has SQS send)
```

**Why This Happened:**
1. Terraform created the new roles with proper permissions
2. `infra/ecs-worker.tf` already specifies the correct role
3. `infra/resources.tf` was reverted to use old role (Option 1 compromise)
4. Terraform was disabled in GitHub Actions, so changes never applied
5. Task definitions still reference old role

---

## **📋 EXECUTION PLAN - PRODUCTION GRADE**

### **Phase 1: Immediate Fix (Manual - 15 minutes)**
**Goal:** Get predictions working RIGHT NOW

1. ✅ **Attach SQS Worker Policy to Old Role (Temporary)**
   - Attach `prod-retainwise-sqs-worker` to `retainwise-ecs-task-role`
   - This gives worker immediate SQS access
   - No redeployment needed
   - **Impact:** Worker can poll SQS immediately

2. ✅ **Verify Backend SQS Policy**
   - Check if `retainwise-ecs-task-role` has `prod-retainwise-sqs-send`
   - If not, attach it
   - **Impact:** Backend can publish to SQS

3. ✅ **Restart Worker Service**
   - Force new deployment to clear error state
   - **Impact:** Worker starts processing messages

**Expected Result:** Predictions work end-to-end within 5 minutes

---

### **Phase 2: Terraform State Management (1-2 hours)**
**Goal:** Get Terraform managing infrastructure properly

4. **Create S3 Backend for Terraform State**
   ```bash
   # Create S3 bucket for state
   aws s3api create-bucket --bucket retainwise-terraform-state \
     --region us-east-1
   
   # Enable versioning
   aws s3api put-bucket-versioning --bucket retainwise-terraform-state \
     --versioning-configuration Status=Enabled
   
   # Enable encryption
   aws s3api put-bucket-encryption --bucket retainwise-terraform-state \
     --server-side-encryption-configuration '{
       "Rules": [{
         "ApplyServerSideEncryptionByDefault": {
           "SSEAlgorithm": "AES256"
         }
       }]
     }'
   
   # Create DynamoDB table for state locking
   aws dynamodb create-table \
     --table-name retainwise-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

5. **Configure Terraform Backend**
   ```hcl
   # infra/backend.tf
   terraform {
     backend "s3" {
       bucket         = "retainwise-terraform-state"
       key            = "prod/terraform.tfstate"
       region         = "us-east-1"
       dynamodb_table = "retainwise-terraform-locks"
       encrypt        = true
     }
   }
   ```

6. **Import Existing Resources**
   ```bash
   cd infra
   terraform init -reconfigure
   
   # Import IAM roles
   terraform import aws_iam_role.backend_task_role prod-retainwise-backend-task-role
   terraform import aws_iam_role.worker_task_role prod-retainwise-worker-task-role
   
   # Import SQS queues
   terraform import aws_sqs_queue.predictions_queue prod-retainwise-predictions-queue
   terraform import aws_sqs_queue.predictions_dlq prod-retainwise-predictions-dlq
   
   # Import policies
   terraform import aws_iam_policy.sqs_send retainwise/prod-retainwise-sqs-send
   terraform import aws_iam_policy.sqs_worker retainwise/prod-retainwise-sqs-worker
   ```

7. **Verify Terraform State**
   ```bash
   terraform plan
   # Should show no changes if imports were successful
   ```

---

### **Phase 3: Update Task Definitions via Terraform (30 minutes)**
**Goal:** Move task definitions to use correct IAM roles

8. **Update resources.tf**
   ```hcl
   resource "aws_ecs_task_definition" "backend" {
     task_role_arn = aws_iam_role.backend_task_role.arn  # Use new role
   }
   ```

9. **Verify ecs-worker.tf**
   ```hcl
   resource "aws_ecs_task_definition" "worker" {
     task_role_arn = aws_iam_role.worker_task_role.arn  # Already correct
   }
   ```

10. **Apply Terraform Changes**
    ```bash
    terraform plan -out=tfplan
    terraform apply tfplan
    ```

11. **Update ECS Services**
    ```bash
    # Backend service will auto-update via GitHub Actions
    # Worker service update
    aws ecs update-service \
      --cluster retainwise-cluster \
      --service retainwise-worker \
      --force-new-deployment
    ```

---

### **Phase 4: CI/CD Integration (1-2 hours)**
**Goal:** Enable automated Terraform deployments

12. **Update GitHub Actions IAM Policy**
    - Add S3 state bucket permissions
    - Add DynamoDB table permissions
    - Ensure `terraform plan` and `terraform apply` can run

13. **Re-enable Terraform in Workflow**
    - Uncomment Terraform steps
    - Add backend configuration
    - Test with a minor change

14. **Document Terraform Workflow**
    - When to run Terraform manually vs. automated
    - How to import new resources
    - State management best practices

---

### **Phase 5: ML Models & End-to-End Testing (30 minutes)**
**Goal:** Complete Task 1.2 functionality

15. **Check ML Model Files**
    ```bash
    ls -la backend/ml/models/
    ```

16. **If Missing, Train Model**
    ```bash
    cd backend/ml
    python train_model.py
    ```

17. **Commit and Deploy**
    ```bash
    git add backend/ml/models/
    git commit -m "feat: Add trained ML models for predictions"
    git push origin main
    ```

18. **End-to-End Testing**
    - Upload CSV file
    - Verify QUEUED → PROCESSING → COMPLETED
    - Download results
    - Verify metrics

---

## **🎯 SUCCESS CRITERIA**

### **Phase 1 Complete When:**
- ✅ Worker logs show: "Successfully received N messages from SQS"
- ✅ Backend logs show: "Successfully published to SQS"
- ✅ Predictions transition: QUEUED → PROCESSING → COMPLETED
- ✅ No IAM AccessDenied errors

### **Phase 2 Complete When:**
- ✅ Terraform state in S3
- ✅ DynamoDB lock table exists
- ✅ `terraform plan` shows no errors
- ✅ All existing resources imported

### **Phase 3 Complete When:**
- ✅ Task definitions use correct IAM roles
- ✅ Services updated to latest task definitions
- ✅ No manual IAM policy attachments needed
- ✅ Terraform manages all IAM resources

### **Phase 4 Complete When:**
- ✅ GitHub Actions can run Terraform
- ✅ Automated deployments work end-to-end
- ✅ Manual Terraform runs still possible
- ✅ Documentation complete

### **Phase 5 Complete When:**
- ✅ ML models deployed
- ✅ Predictions produce actual churn scores
- ✅ Results downloadable from S3
- ✅ Task 1.2 COMPLETE

---

## **⚠️ ROLLBACK PLAN**

If anything goes wrong:

1. **Phase 1 Rollback:**
   - Detach temporary policies from old role
   - Worker will go back to error state (reversible)

2. **Phase 2 Rollback:**
   - Delete S3 state bucket
   - Delete DynamoDB table
   - Continue with local Terraform state

3. **Phase 3 Rollback:**
   - Revert task definitions to previous revision
   - `aws ecs update-service --task-definition <old-revision>`

4. **Phase 4 Rollback:**
   - Re-disable Terraform in GitHub Actions
   - Manual deployments only

---

## **📊 ESTIMATED TIMELINE**

| Phase | Duration | Can Start | Dependencies |
|-------|----------|-----------|--------------|
| Phase 1 | 15 min | NOW | None |
| Phase 2 | 1-2 hours | After Phase 1 | AWS credentials |
| Phase 3 | 30 min | After Phase 2 | Terraform state |
| Phase 4 | 1-2 hours | After Phase 3 | GitHub repo access |
| Phase 5 | 30 min | After Phase 1 | Phase 1 complete |

**Total Time:** 3-5 hours for complete production-grade setup  
**Minimum Time to Working System:** 15 minutes (Phase 1 only)

---

## **🚀 EXECUTION STATUS**

- [ ] Phase 1: Immediate Fix
- [ ] Phase 2: Terraform State Management
- [ ] Phase 3: Task Definitions via Terraform
- [ ] Phase 4: CI/CD Integration
- [ ] Phase 5: ML Models & Testing

**Current Phase:** Phase 1 - Starting Now

---

**Next Action:** Attach SQS policies to old role for immediate fix

