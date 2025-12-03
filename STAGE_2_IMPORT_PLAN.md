# Stage 2: Resource Import Plan

## Resources Audit Complete

### ✅ Resources That EXIST in AWS (Manually Created):

#### **IAM Roles (7 total):**
1. `prod-retainwise-backend-task-role` → Terraform: `aws_iam_role.backend_task_role`
2. `prod-retainwise-worker-task-role` → Terraform: `aws_iam_role.worker_task_role`
3. `retainwise-cicd-ecs-deployment-role` → Terraform: `aws_iam_role.cicd_ecs_deployment`
4. `retainwise-ecs-task-execution-role` → Terraform: `aws_iam_role.ecs_task_execution`
5. `retainwise-ecs-task-role` → Terraform: `aws_iam_role.ecs_task`
6. `retainwise-lambda-ecs-scaling-role` → Terraform: `aws_iam_role.lambda_ecs_scaling`
7. `retainwise-lambda-td-guardrail-role` → Terraform: `aws_iam_role.lambda_td_guardrail`

#### **IAM Policies (9 total):**
1. `prod-retainwise-sqs-send` → Terraform: `aws_iam_policy.sqs_send_policy`
2. `prod-retainwise-sqs-worker` → Terraform: `aws_iam_policy.sqs_worker_policy`
3. `retainwise-s3-access` → Terraform: `aws_iam_policy.s3_access`
4. `retainwise-worker-permissions` → Terraform: `aws_iam_policy.worker_permissions`
5. `retainwise-cicd-ecs-deployment-restricted` → Terraform: `aws_iam_policy.cicd_ecs_deployment`
6. `retainwise-deny-ecs-td-changes` → Terraform: `aws_iam_policy.deny_ecs_task_definition_changes`
7. `retainwise-secrets-manager-access` → Terraform: `aws_iam_policy.secrets_manager_access`
8. `retainwise-lambda-ecs-scaling-policy` → Terraform: `aws_iam_policy.lambda_ecs_scaling`
9. `retainwise-lambda-td-guardrail-policy` → Terraform: `aws_iam_policy.lambda_td_guardrail`

#### **SQS Queues (2 total):**
1. `prod-retainwise-predictions-queue` → Terraform: `aws_sqs_queue.predictions_queue`
2. `prod-retainwise-predictions-dlq` → Terraform: `aws_sqs_queue.predictions_dlq`

#### **S3 Buckets (2 total):**
1. `retainwise-uploads-908226940571` → Terraform: `aws_s3_bucket.uploads`
2. `retainwise-terraform-state-prod` → **DO NOT IMPORT** (backend state bucket)

### ⚠️ CRITICAL ISSUE DISCOVERED:

**Problem:** Terraform resource definitions ALREADY EXIST but resources were created manually!

**Impact:** If we run `terraform apply` now, it will try to create duplicates → FAIL

**Solution:** We must IMPORT existing resources BEFORE any terraform apply

---

## Import Strategy:

### **Phase 1: Import Core IAM Roles (Task Roles)**
- These are referenced by other resources
- Must be imported first to avoid dependency errors

### **Phase 2: Import IAM Policies**
- After roles, import policies

### **Phase 3: Import Policy Attachments**
- Link policies to roles in Terraform state

### **Phase 4: Import SQS Queues**
- Import main queue and DLQ
- Queue policies will be created by Terraform (not manual)

### **Phase 5: Import S3 Bucket**
- Import uploads bucket
- DO NOT import state bucket (special case)

### **Phase 6: Verify & Test**
- Run `terraform plan`
- Should show "No changes" or minor formatting differences
- Fix any discrepancies

---

## Import Commands Ready:

### IAM Roles:
```bash
terraform import aws_iam_role.backend_task_role prod-retainwise-backend-task-role
terraform import aws_iam_role.worker_task_role prod-retainwise-worker-task-role
terraform import aws_iam_role.ecs_task_execution retainwise-ecs-task-execution-role
terraform import aws_iam_role.ecs_task retainwise-ecs-task-role
terraform import aws_iam_role.cicd_ecs_deployment retainwise-cicd-ecs-deployment-role
terraform import aws_iam_role.lambda_ecs_scaling retainwise-lambda-ecs-scaling-role
terraform import aws_iam_role.lambda_td_guardrail retainwise-lambda-td-guardrail-role
```

### IAM Policies:
```bash
terraform import aws_iam_policy.sqs_send_policy arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-send
terraform import aws_iam_policy.sqs_worker_policy arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-worker
terraform import aws_iam_policy.s3_access arn:aws:iam::908226940571:policy/retainwise-s3-access
terraform import aws_iam_policy.worker_permissions arn:aws:iam::908226940571:policy/retainwise-worker-permissions
terraform import aws_iam_policy.cicd_ecs_deployment arn:aws:iam::908226940571:policy/retainwise-cicd-ecs-deployment-restricted
terraform import aws_iam_policy.deny_ecs_task_definition_changes arn:aws:iam::908226940571:policy/retainwise-deny-ecs-td-changes
terraform import aws_iam_policy.secrets_manager_access arn:aws:iam::908226940571:policy/retainwise-secrets-manager-access
terraform import aws_iam_policy.lambda_ecs_scaling arn:aws:iam::908226940571:policy/retainwise-lambda-ecs-scaling-policy
terraform import aws_iam_policy.lambda_td_guardrail arn:aws:iam::908226940571:policy/retainwise-lambda-td-guardrail-policy
```

### SQS Queues:
```bash
terraform import aws_sqs_queue.predictions_queue https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue
terraform import aws_sqs_queue.predictions_dlq https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-dlq
```

### S3 Buckets:
```bash
terraform import aws_s3_bucket.uploads retainwise-uploads-908226940571
```

---

## Status: Ready to Execute

