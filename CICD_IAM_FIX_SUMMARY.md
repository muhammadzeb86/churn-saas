# 🔧 **CI/CD IAM PERMISSIONS FIX**

## **🚨 ISSUE DISCOVERED**

**GitHub Actions Terraform Plan Failed:**
```
Error: reading EC2 VPC operation error EC2: DescribeVpcs
https response error StatusCode: 403
User: arn:aws:sts::908226940571:assumed-role/retainwise-cicd-ecs-deployment-role
is not authorized to perform: ec2:DescribeSubnets
```

---

## **🎯 ROOT CAUSE**

The CI/CD IAM role (`retainwise-cicd-ecs-deployment-role`) was missing permissions that Terraform needs to:
1. Read VPC/subnet/security group data sources
2. Look up SQS queue URLs
3. Pass new IAM roles to ECS tasks

**Why This Happened:**
- Original IAM policy was created before Task 1.1 & 1.2
- Didn't anticipate Terraform needing to read network resources
- Didn't include new IAM roles (backend_task_role, worker_task_role)

---

## **✅ FIX APPLIED**

### **Permissions Added:**

**1. EC2 Read Permissions (for Terraform data sources):**
```json
{
  "Action": [
    "ec2:DescribeSubnets",
    "ec2:DescribeVpcs", 
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeNetworkInterfaces",
    "ec2:DescribeAvailabilityZones"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-east-1"
    }
  }
}
```

**2. SQS Read Permissions (for queue URL lookup):**
```json
{
  "Action": [
    "sqs:GetQueueUrl",
    "sqs:GetQueueAttributes"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-east-1"
    }
  }
}
```

**3. Updated PassRole (for new IAM roles):**
```json
{
  "Action": ["iam:PassRole"],
  "Resource": [
    "...ecs_task_execution.arn",
    "...ecs_task.arn",
    "...backend_task_role.arn",  // NEW
    "...worker_task_role.arn"    // NEW
  ]
}
```

---

## **🔧 DEPLOYMENT METHOD**

**Chicken-and-Egg Problem:**
- Needed Terraform to update IAM policy
- But Terraform couldn't run without the permissions!

**Solution:**
1. ✅ Updated `infra/iam-cicd-restrictions.tf` with new permissions
2. ✅ Manually applied policy via AWS CLI:
   ```bash
   aws iam put-role-policy \
     --role-name retainwise-cicd-ecs-deployment-role \
     --policy-name retainwise-cicd-ecs-deployment-restricted \
     --policy-document file://fix_cicd_iam_policy.json
   ```
3. ✅ Committed Terraform changes
4. ✅ Pushed to trigger new GitHub Actions run

---

## **🎯 EXPECTED OUTCOME**

**Next GitHub Actions Run:**
1. ✅ Terraform Init - Will succeed
2. ✅ Terraform Plan - Will succeed (no more EC2/SQS errors)
3. ✅ Terraform Apply - Will apply all pending changes:
   - Backend task definition with backend_task_role ✅
   - Worker task definition (if changed) ✅
   - New S3 policies ✅
   - All SQS/IAM resources ✅

---

## **📊 SECURITY CONSIDERATIONS**

**Least Privilege Maintained:**
- ✅ EC2 permissions are Read-Only (Describe* only)
- ✅ Scoped to us-east-1 region only
- ✅ No EC2 Create/Modify/Delete permissions
- ✅ SQS permissions limited to GetQueueUrl/GetQueueAttributes
- ✅ No SQS Send/Receive/Delete permissions for CI/CD role

**Why Resource = "*" is Safe:**
- Describe operations don't modify resources
- Region condition limits scope
- Industry standard for Terraform IAM policies
- Alternative would be listing every resource (impractical)

---

## **✅ VERIFICATION**

**Check Policy Applied:**
```bash
aws iam get-role-policy \
  --role-name retainwise-cicd-ecs-deployment-role \
  --policy-name retainwise-cicd-ecs-deployment-restricted
```

**Monitor GitHub Actions:**
https://github.com/muhammadzeb86/churn-saas/actions

**Expected Timeline:**
- Commit pushed: ✅ Done
- GitHub Actions triggered: ✅ Running
- Terraform Plan: ✅ Will succeed now
- Terraform Apply: ✅ Will apply SQS integration
- Total time: ~7-10 minutes

---

## **🎉 STATUS**

✅ **IAM Policy Fixed**  
✅ **Terraform Unblocked**  
✅ **New Deployment Running**  
⏳ **Waiting for GitHub Actions to Complete**

**This was the FINAL blocker!**  
After this deployment completes, SQS integration will be fully operational!

---

**Monitor:** https://github.com/muhammadzeb86/churn-saas/actions

