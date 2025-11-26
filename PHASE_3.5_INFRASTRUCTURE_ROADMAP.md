# 🏗️ Phase 3.5: Infrastructure Hardening - Complete Roadmap

**Date Created:** November 26, 2025  
**Status:** READY TO BEGIN  
**Priority:** HIGH - Foundation for all future development

---

## 📊 **EXECUTIVE SUMMARY**

### **Current State:**
- ✅ Task 1.1 Complete: SQS queue infrastructure
- ✅ Task 1.2 Complete: ML worker service deployed
- ⚠️ Infrastructure managed manually (AWS Console/CLI)
- ⚠️ No Terraform state management
- ⚠️ CI/CD Terraform disabled (quick fixes prioritized)

### **Target State:**
- ✅ All infrastructure as code (Terraform)
- ✅ Automated deployments with proper CI/CD
- ✅ State management in S3 with locking
- ✅ Reproducible, documented, auditable infrastructure
- ✅ Ready for production scale and team collaboration

### **Timeline:** 3-5 days (20-30 hours)

---

## 🎯 **STRATEGIC OBJECTIVES**

1. **Eliminate Technical Debt:** Clean up manual IAM policies, task definitions
2. **Enable Team Collaboration:** Terraform state in S3 allows multiple developers
3. **Ensure Reproducibility:** Disaster recovery becomes trivial
4. **Improve Security:** Proper IAM roles, VPC endpoints, least privilege
5. **Accelerate Future Development:** Infrastructure changes via code review

---

## 📋 **PHASE 3.5 BREAKDOWN**

### **Stage 1: Terraform State Foundation (Day 1 - 4 hours)**

#### **Objective:**
Set up S3 backend for Terraform state with DynamoDB locking.

#### **Tasks:**

**1.1 Create S3 State Bucket**
```bash
# Create bucket for Terraform state
aws s3api create-bucket \
  --bucket retainwise-terraform-state-prod \
  --region us-east-1

# Enable versioning (disaster recovery)
aws s3api put-bucket-versioning \
  --bucket retainwise-terraform-state-prod \
  --versioning-configuration Status=Enabled

# Enable encryption at rest
aws s3api put-bucket-encryption \
  --bucket retainwise-terraform-state-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

# Block public access (security)
aws s3api put-public-access-block \
  --bucket retainwise-terraform-state-prod \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable lifecycle policy (optional - cost optimization)
aws s3api put-bucket-lifecycle-configuration \
  --bucket retainwise-terraform-state-prod \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "DeleteOldVersions",
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {"Days": 90}
    }]
  }'
```

**1.2 Create DynamoDB Lock Table**
```bash
aws dynamodb create-table \
  --table-name retainwise-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --tags Key=Project,Value=RetainWise Key=ManagedBy,Value=Terraform
```

**1.3 Configure Terraform Backend**

Create `infra/backend.tf`:
```hcl
terraform {
  backend "s3" {
    bucket         = "retainwise-terraform-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "retainwise-terraform-locks"
    
    # Prevent accidental deletion/modification
    skip_region_validation      = false
    skip_credentials_validation = false
    skip_metadata_api_check     = false
  }
  
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

**1.4 Initialize Terraform with Backend**
```bash
cd infra
terraform init -reconfigure

# Verify state is in S3
aws s3 ls s3://retainwise-terraform-state-prod/prod/
```

**✅ Success Criteria:**
- S3 bucket exists with versioning and encryption
- DynamoDB table created
- `terraform init` succeeds
- State file visible in S3

---

### **Stage 2: Import Existing Resources (Day 1-2 - 8 hours)**

#### **Objective:**
Import all manually-created AWS resources into Terraform state.

#### **Resources to Import:**

**2.1 IAM Roles & Policies**
```bash
# Task roles
terraform import aws_iam_role.backend_task_role prod-retainwise-backend-task-role
terraform import aws_iam_role.worker_task_role prod-retainwise-worker-task-role

# Policies
terraform import aws_iam_policy.sqs_send retainwise/prod-retainwise-sqs-send
terraform import aws_iam_policy.sqs_worker retainwise/prod-retainwise-sqs-worker

# Policy attachments
terraform import aws_iam_role_policy_attachment.backend_sqs_send prod-retainwise-backend-task-role/arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-send
terraform import aws_iam_role_policy_attachment.worker_sqs prod-retainwise-worker-task-role/arn:aws:iam::908226940571:policy/retainwise/prod-retainwise-sqs-worker
```

**2.2 SQS Queues**
```bash
terraform import aws_sqs_queue.predictions_queue https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue
terraform import aws_sqs_queue.predictions_dlq https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-dlq
```

**2.3 ECS Task Definitions**
```bash
# Note: Task definitions are immutable - don't import, let Terraform manage new revisions
# Document current revisions for reference:
# - retainwise-backend:86
# - retainwise-worker:2
```

**2.4 S3 Buckets (if not already in Terraform)**
```bash
terraform import aws_s3_bucket.uploads retainwise-uploads
terraform import aws_s3_bucket.predictions retainwise-predictions # if separate
```

**2.5 ECR Repositories**
```bash
terraform import aws_ecr_repository.backend retainwise-backend
```

**2.6 Verify Import**
```bash
terraform plan

# Should show: No changes. Infrastructure is up-to-date.
# If it shows changes, adjust Terraform code to match actual state
```

**✅ Success Criteria:**
- All resources imported successfully
- `terraform plan` shows no changes
- State file contains all resources

---

### **Stage 3: Define Missing Resources in Terraform (Day 2 - 4 hours)**

#### **Objective:**
Ensure ALL infrastructure is defined in Terraform code.

#### **Tasks:**

**3.1 Update IAM Role Definitions**

Create `infra/iam-task-roles.tf`:
```hcl
# Backend Task Role
resource "aws_iam_role" "backend_task_role" {
  name = "prod-retainwise-backend-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Project    = "RetainWise"
    ManagedBy  = "Terraform"
    Environment = var.environment
  }
}

# SQS Send Policy for Backend
resource "aws_iam_policy" "sqs_send" {
  name        = "prod-retainwise-sqs-send"
  path        = "/retainwise/"
  description = "Allow backend to publish messages to SQS predictions queue"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowSendToPredictionsQueue"
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ]
      Resource = [
        aws_sqs_queue.predictions_queue.arn
      ]
    }]
  })
}

# Attach policies
resource "aws_iam_role_policy_attachment" "backend_sqs_send" {
  role       = aws_iam_role.backend_task_role.name
  policy_arn = aws_iam_policy.sqs_send.arn
}

resource "aws_iam_role_policy_attachment" "backend_s3" {
  role       = aws_iam_role.backend_task_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# Worker Task Role
resource "aws_iam_role" "worker_task_role" {
  name = "prod-retainwise-worker-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Project    = "RetainWise"
    ManagedBy  = "Terraform"
    Environment = var.environment
  }
}

# SQS Worker Policy
resource "aws_iam_policy" "sqs_worker" {
  name        = "prod-retainwise-sqs-worker"
  path        = "/retainwise/"
  description = "Allow worker to receive/delete messages from SQS queues"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowWorkerQueueOperations"
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ]
      Resource = [
        aws_sqs_queue.predictions_queue.arn,
        aws_sqs_queue.predictions_dlq.arn
      ]
    }]
  })
}

# Attach policies
resource "aws_iam_role_policy_attachment" "worker_sqs" {
  role       = aws_iam_role.worker_task_role.name
  policy_arn = aws_iam_policy.sqs_worker.arn
}

resource "aws_iam_role_policy_attachment" "worker_s3" {
  role       = aws_iam_role.worker_task_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}
```

**3.2 Update Task Definitions to Use New Roles**

Update `infra/resources.tf`:
```hcl
resource "aws_ecs_task_definition" "backend" {
  # ... existing config ...
  task_role_arn = aws_iam_role.backend_task_role.arn  # Use new role
}
```

Update `infra/ecs-worker.tf`:
```hcl
resource "aws_ecs_task_definition" "worker" {
  # ... existing config ...
  task_role_arn = aws_iam_role.worker_task_role.arn  # Already correct
}
```

**3.3 Add VPC Endpoint for SQS (Proper Solution)**

Create `infra/vpc-endpoints.tf`:
```hcl
# Get route tables for VPC
data "aws_route_tables" "main" {
  vpc_id = data.aws_vpc.main.id
}

# SQS VPC Endpoint (Gateway type)
resource "aws_vpc_endpoint" "sqs" {
  vpc_id       = data.aws_vpc.main.id
  service_name = "com.amazonaws.${var.aws_region}.sqs"
  
  vpc_endpoint_type = "Interface"
  
  subnet_ids = [
    data.aws_subnet.private_1.id,
    data.aws_subnet.private_2.id
  ]
  
  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]
  
  private_dns_enabled = true
  
  tags = {
    Name       = "retainwise-sqs-endpoint"
    Project    = "RetainWise"
    ManagedBy  = "Terraform"
    Environment = var.environment
  }
}

# Security group for VPC endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "retainwise-vpc-endpoints"
  description = "Security group for VPC endpoints"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
    description = "Allow HTTPS from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name       = "retainwise-vpc-endpoints"
    Project    = "RetainWise"
    ManagedBy  = "Terraform"
  }
}
```

**3.4 Add VPC Conditions Back to IAM Policies (After VPC Endpoint)**

Update policies to include VPC condition:
```hcl
# In iam-task-roles.tf, update policies:
policy = jsonencode({
  Version = "2012-10-17"
  Statement = [{
    Sid    = "AllowSendToPredictionsQueue"
    Effect = "Allow"
    Action = [
      "sqs:SendMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ]
    Resource = [
      aws_sqs_queue.predictions_queue.arn
    ]
    Condition = {
      StringEquals = {
        "aws:SourceVpc" = data.aws_vpc.main.id
      }
    }
  }]
})
```

**✅ Success Criteria:**
- All IAM resources defined in Terraform
- VPC endpoint created for SQS
- `terraform plan` shows intended changes
- Code review passes

---

### **Stage 4: CI/CD IAM Permissions Fix (Day 2-3 - 4 hours)**

#### **Objective:**
Give GitHub Actions proper permissions to run Terraform.

#### **Tasks:**

**4.1 Create Comprehensive CI/CD Policy**

Create `infra/iam-cicd.tf`:
```hcl
# CI/CD User/Role (choose one based on your setup)
data "aws_iam_role" "github_actions" {
  name = "retainwise-github-actions-role"  # Adjust if needed
}

# Comprehensive Terraform Management Policy
resource "aws_iam_policy" "cicd_terraform" {
  name        = "retainwise-cicd-terraform-full"
  path        = "/retainwise/"
  description = "Full permissions for CI/CD to manage infrastructure via Terraform"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Terraform State Access
      {
        Sid    = "TerraformStateAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::retainwise-terraform-state-prod",
          "arn:aws:s3:::retainwise-terraform-state-prod/*"
        ]
      },
      # DynamoDB Locking
      {
        Sid    = "TerraformStateLocking"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:us-east-1:908226940571:table/retainwise-terraform-locks"
      },
      # IAM Management
      {
        Sid    = "IAMManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:ListRoles",
          "iam:UpdateRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicies",
          "iam:ListPolicyVersions",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:PutRolePolicy",
          "iam:GetRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:PassRole"
        ]
        Resource = [
          "arn:aws:iam::908226940571:role/retainwise-*",
          "arn:aws:iam::908226940571:role/*/retainwise-*",
          "arn:aws:iam::908226940571:policy/retainwise/*"
        ]
      },
      # ECS Management
      {
        Sid    = "ECSManagement"
        Effect = "Allow"
        Action = [
          "ecs:*"
        ]
        Resource = "*"
      },
      # ECR Management
      {
        Sid    = "ECRManagement"
        Effect = "Allow"
        Action = [
          "ecr:*"
        ]
        Resource = "*"
      },
      # SQS Management
      {
        Sid    = "SQSManagement"
        Effect = "Allow"
        Action = [
          "sqs:CreateQueue",
          "sqs:DeleteQueue",
          "sqs:GetQueueAttributes",
          "sqs:SetQueueAttributes",
          "sqs:ListQueues",
          "sqs:TagQueue",
          "sqs:UntagQueue",
          "sqs:ListQueueTags"
        ]
        Resource = "arn:aws:sqs:us-east-1:908226940571:*retainwise*"
      },
      # S3 Management
      {
        Sid    = "S3Management"
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
          "s3:GetBucketEncryption",
          "s3:PutBucketEncryption",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutBucketPublicAccessBlock",
          "s3:GetBucketTagging",
          "s3:PutBucketTagging",
          "s3:GetBucketCors",
          "s3:PutBucketCors",
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::retainwise-*"
      },
      # VPC/Networking Read
      {
        Sid    = "VPCRead"
        Effect = "Allow"
        Action = [
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeRouteTables",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeVpcAttribute",
          "ec2:DescribeNetworkInterfaces"
        ]
        Resource = "*"
      },
      # VPC Endpoint Management
      {
        Sid    = "VPCEndpointManagement"
        Effect = "Allow"
        Action = [
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoint",
          "ec2:ModifyVpcEndpoint",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "*"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogsManagement"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:PutRetentionPolicy",
          "logs:TagLogGroup",
          "logs:UntagLogGroup",
          "logs:DescribeLogGroups"
        ]
        Resource = "arn:aws:logs:us-east-1:908226940571:log-group:/ecs/retainwise-*"
      }
    ]
  })
}

# Attach policy to CI/CD role
resource "aws_iam_role_policy_attachment" "github_terraform" {
  role       = data.aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.cicd_terraform.arn
}
```

**4.2 Apply IAM Changes**
```bash
# This is a chicken-and-egg problem - we need permissions to update permissions
# Solution: Apply IAM changes manually first, then let Terraform manage

terraform apply -target=aws_iam_policy.cicd_terraform
terraform apply -target=aws_iam_role_policy_attachment.github_terraform
```

**✅ Success Criteria:**
- CI/CD role has comprehensive permissions
- `terraform plan` runs without permission errors
- No overly broad permissions (principle of least privilege)

---

### **Stage 5: Re-enable Terraform in GitHub Actions (Day 3 - 2 hours)**

#### **Objective:**
Restore automated Terraform runs in CI/CD pipeline.

#### **Tasks:**

**5.1 Update GitHub Actions Workflow**

Update `.github/workflows/backend-ci-cd.yml`:
```yaml
# Uncomment Terraform steps
- name: Terraform Init
  working-directory: ./infra
  run: terraform init

- name: Terraform Format Check
  working-directory: ./infra
  run: terraform fmt -check

- name: Terraform Validate
  working-directory: ./infra
  run: terraform validate

- name: Terraform Plan
  working-directory: ./infra
  run: |
    terraform plan -out=tfplan
    terraform show -no-color tfplan > plan.txt

- name: Comment Terraform Plan on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v6
  with:
    script: |
      const fs = require('fs');
      const plan = fs.readFileSync('infra/plan.txt', 'utf8');
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `## Terraform Plan\n\`\`\`\n${plan}\n\`\`\``
      });

- name: Terraform Apply
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  working-directory: ./infra
  run: terraform apply -auto-approve tfplan
```

**5.2 Add Terraform Formatting Pre-commit Hook**

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.83.5
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: terraform_docs
```

**5.3 Test Terraform in CI/CD**
```bash
# Make a minor change to test
echo "# Terraform managed" >> infra/README.md
git add infra/README.md
git commit -m "test: Verify Terraform CI/CD"
git push origin main

# Monitor GitHub Actions
```

**✅ Success Criteria:**
- Terraform runs in GitHub Actions
- Plan shown on PRs
- Apply runs on main branch
- No permission errors

---

### **Stage 6: Worker Deployment Automation (Day 3-4 - 3 hours)**

#### **Objective:**
Automate worker service deployment in GitHub Actions.

#### **Tasks:**

**6.1 Update GitHub Actions to Deploy Worker**

Update `.github/workflows/backend-ci-cd.yml`:
```yaml
# After backend deployment, add worker deployment

- name: Update Worker Service
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: |
    echo "🔄 Registering worker task definition..."
    
    # Get latest backend image tag (they share the same image)
    IMAGE_TAG="${{ github.sha }}"
    IMAGE_URI="${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/retainwise-backend:${IMAGE_TAG}"
    
    # Get current worker task definition
    TASK_DEF=$(aws ecs describe-task-definition \
      --task-definition retainwise-worker \
      --query 'taskDefinition' \
      --output json)
    
    # Update image in task definition
    NEW_TASK_DEF=$(echo $TASK_DEF | jq --arg IMAGE "$IMAGE_URI" \
      '.containerDefinitions[0].image = $IMAGE' | \
      jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')
    
    # Register new task definition
    NEW_TASK_ARN=$(echo $NEW_TASK_DEF | \
      aws ecs register-task-definition --cli-input-json file:///dev/stdin | \
      jq -r '.taskDefinition.taskDefinitionArn')
    
    echo "✅ New worker task definition: $NEW_TASK_ARN"
    
    # Update worker service
    echo "🚀 Deploying worker service..."
    aws ecs update-service \
      --cluster retainwise-cluster \
      --service retainwise-worker \
      --task-definition retainwise-worker \
      --force-new-deployment
    
    echo "✅ Worker service deployment initiated"
```

**6.2 Add Worker Health Check**
```yaml
- name: Wait for Worker Deployment
  run: |
    echo "⏳ Waiting for worker deployment to complete..."
    aws ecs wait services-stable \
      --cluster retainwise-cluster \
      --services retainwise-worker
    echo "✅ Worker deployment complete"
```

**✅ Success Criteria:**
- Worker deploys automatically after backend
- Both services use same Docker image
- Deployment waits for stability
- Logs show successful deployment

---

### **Stage 7: Documentation & Cleanup (Day 4-5 - 4 hours)**

#### **Objective:**
Document everything and clean up technical debt.

#### **Tasks:**

**7.1 Create Infrastructure Documentation**

Create `infra/README.md`:
```markdown
# RetainWise Infrastructure

## Overview
This directory contains all infrastructure-as-code (IaC) for RetainWise Analytics.

## Architecture
- **Compute:** ECS Fargate (backend API + worker service)
- **Storage:** S3 (uploads, predictions), RDS PostgreSQL (metadata)
- **Queue:** SQS (prediction tasks)
- **Container Registry:** ECR
- **Monitoring:** CloudWatch

## Directory Structure
- `resources.tf` - Main ECS, ALB, and networking resources
- `ecs-worker.tf` - Worker service configuration
- `sqs.tf` - SQS queues and DLQ
- `iam-task-roles.tf` - IAM roles for ECS tasks
- `iam-cicd.tf` - IAM roles for CI/CD
- `vpc-endpoints.tf` - VPC endpoints for AWS services
- `backend.tf` - Terraform S3 backend configuration
- `variables.tf` - Input variables
- `outputs.tf` - Output values

## Prerequisites
- AWS CLI configured
- Terraform >= 1.0
- Access to `retainwise-terraform-state-prod` S3 bucket

## Usage

### Initialize
\`\`\`bash
terraform init
\`\`\`

### Plan Changes
\`\`\`bash
terraform plan -out=tfplan
\`\`\`

### Apply Changes
\`\`\`bash
terraform apply tfplan
\`\`\`

### View State
\`\`\`bash
terraform state list
terraform state show aws_ecs_service.backend
\`\`\`

## Manual Operations

### Import Existing Resource
\`\`\`bash
terraform import aws_sqs_queue.example https://sqs.region.amazonaws.com/account/queue-name
\`\`\`

### Force Worker Redeployment
\`\`\`bash
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --force-new-deployment
\`\`\`

## Disaster Recovery

### Restore from Backup
\`\`\`bash
# List available state versions
aws s3api list-object-versions \
  --bucket retainwise-terraform-state-prod \
  --prefix prod/terraform.tfstate

# Download specific version
aws s3api get-object \
  --bucket retainwise-terraform-state-prod \
  --key prod/terraform.tfstate \
  --version-id <VERSION_ID> \
  terraform.tfstate.backup

# Copy to current state
aws s3 cp terraform.tfstate.backup \
  s3://retainwise-terraform-state-prod/prod/terraform.tfstate
\`\`\`

## Security Notes
- State file contains secrets - S3 bucket has encryption and restricted access
- IAM roles follow least privilege principle
- VPC endpoints used for AWS service access (no internet egress)
- All resources tagged for audit and cost tracking

## Troubleshooting

### Terraform State Locked
\`\`\`bash
# Check DynamoDB for lock
aws dynamodb scan --table-name retainwise-terraform-locks

# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
\`\`\`

### Permission Denied
\`\`\`bash
# Verify AWS credentials
aws sts get-caller-identity

# Check IAM role permissions
aws iam list-attached-role-policies --role-name <ROLE_NAME>
\`\`\`
```

**7.2 Update Master Plan**

Update `ML_IMPLEMENTATION_MASTER_PLAN.md`:
```markdown
## Phase 3.5: Infrastructure Hardening ✅ COMPLETE

### Objectives
- [x] Terraform state management (S3 + DynamoDB)
- [x] Import all manual resources into Terraform
- [x] VPC endpoints for AWS services
- [x] CI/CD IAM permissions fixed
- [x] Automated worker deployment
- [x] Comprehensive documentation

### Outcomes
- Infrastructure fully managed by Terraform
- Reproducible deployments
- Ready for team collaboration
- Foundation for Phase 4 (Visualizations)
```

**7.3 Clean Up Manual Resources**

Remove manual overrides and temporary fixes:
```bash
# Remove temporary policy files
rm sqs-send-policy.json
rm sqs-worker-policy.json
rm fix_sqs_env_vars.ps1

# Archive old documentation
mkdir docs/archive
mv TASK_1.2_CRITICAL_FIX_REQUIRED.md docs/archive/
mv SQS_PERMISSIONS_FIX.md docs/archive/

# Clean up git
git add -A
git commit -m "chore: Clean up Phase 3.5 temporary files"
```

**7.4 Create Runbook**

Create `docs/RUNBOOK.md`:
```markdown
# RetainWise Operations Runbook

## Common Operations

### Deploy Code Changes
\`\`\`bash
# Automatic via GitHub Actions on push to main
git push origin main
\`\`\`

### Manual Worker Redeploy
\`\`\`bash
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --force-new-deployment
\`\`\`

### Check Service Health
\`\`\`bash
# Backend
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-backend

# Worker
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-worker

# SQS Queue Depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue \
  --attribute-names ApproximateNumberOfMessages
\`\`\`

### Scale Services
\`\`\`bash
# Scale backend
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-backend \
  --desired-count 2

# Scale worker
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --desired-count 3
\`\`\`

### View Logs
\`\`\`bash
# Recent backend logs
aws logs tail /ecs/retainwise-backend --follow

# Recent worker logs
aws logs tail /ecs/retainwise-worker --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /ecs/retainwise-backend \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
\`\`\`

## Incident Response

### Backend Service Down
1. Check service status
2. Check task logs for errors
3. Verify database connectivity
4. Check ALB health checks
5. Rollback if needed

### Worker Not Processing
1. Check worker logs
2. Verify SQS queue exists
3. Check IAM permissions
4. Verify ML model files present
5. Force redeploy worker

### Database Migration Failed
1. Check migration logs
2. Verify database connectivity
3. Check Alembic version
4. Manual rollback if needed
5. Re-run migration

## Monitoring

### Key Metrics
- ECS service desired vs. running count
- ALB target health status
- SQS queue depth and age
- Database connections
- Error rates in logs

### Alerts (TODO: Set up CloudWatch Alarms)
- Service unhealthy
- High error rate
- Queue depth > threshold
- Database connection failures
```

**✅ Success Criteria:**
- All documentation complete and accurate
- Manual overrides removed
- Runbook tested
- Team can operate infrastructure independently

---

## 📊 **VERIFICATION & TESTING**

### **Stage 8: Comprehensive Testing (Day 5 - 3 hours)**

#### **End-to-End Tests:**

**8.1 Infrastructure Tests**
```bash
# Verify Terraform state
terraform plan  # Should show no changes

# Verify all resources exist
terraform state list

# Verify outputs
terraform output -json
```

**8.2 Deployment Tests**
```bash
# Make a trivial change
echo "# Test comment" >> backend/main.py

# Commit and push
git add backend/main.py
git commit -m "test: Verify automated deployment"
git push origin main

# Monitor GitHub Actions
# Verify both backend and worker deploy
# Verify services reach steady state
```

**8.3 Functional Tests**
```bash
# Upload CSV
# Verify prediction completes
# Check worker logs show processing
# Verify results in database
```

**8.4 Disaster Recovery Test**
```bash
# Simulate state corruption
# Restore from S3 backup
# Verify terraform still works
```

**✅ Success Criteria:**
- All tests pass
- Infrastructure reproducible
- Deployments automated
- Documentation accurate

---

## 📈 **SUCCESS METRICS**

### **Technical Metrics:**
- ✅ 100% of infrastructure in Terraform
- ✅ Zero manual AWS Console changes required
- ✅ Terraform state in S3 with locking
- ✅ CI/CD runs without manual intervention
- ✅ Worker deploys automatically

### **Operational Metrics:**
- ✅ Time to deploy: < 10 minutes (automated)
- ✅ Time to rollback: < 5 minutes
- ✅ Infrastructure drift: 0%
- ✅ Documentation coverage: 100%

### **Business Metrics:**
- ✅ Ready for team collaboration
- ✅ Ready for production launch
- ✅ Reproducible in any AWS account
- ✅ Audit trail for all changes

---

## 🎯 **NEXT STEPS AFTER PHASE 3.5**

### **Immediate (Fix Download CSV):**
- Worker needs to set `s3_output_key` after processing
- 30 minutes to implement
- Makes predictions fully functional

### **Phase 4: Visualizations & Insights**
- Customer segmentation charts
- Churn prediction trends
- Model performance metrics
- Real-time dashboard

### **Phase 5: Advanced Features**
- A/B testing framework
- Model retraining pipeline
- Multi-model support
- Advanced analytics

---

## 📋 **DAILY CHECKLIST**

### **Day 1: Foundation**
- [ ] Create S3 state bucket
- [ ] Create DynamoDB lock table
- [ ] Configure Terraform backend
- [ ] Initialize Terraform with backend
- [ ] Import IAM roles and policies
- [ ] Import SQS queues

### **Day 2: Resources**
- [ ] Define IAM resources in Terraform
- [ ] Import remaining resources
- [ ] Verify terraform plan shows no changes
- [ ] Create VPC endpoint for SQS
- [ ] Update IAM policies with VPC conditions

### **Day 3: CI/CD**
- [ ] Create comprehensive CI/CD IAM policy
- [ ] Apply IAM changes
- [ ] Re-enable Terraform in GitHub Actions
- [ ] Test Terraform CI/CD
- [ ] Add worker deployment automation

### **Day 4: Testing**
- [ ] End-to-end deployment test
- [ ] Infrastructure verification
- [ ] Disaster recovery test
- [ ] Performance validation

### **Day 5: Documentation**
- [ ] Create infrastructure README
- [ ] Create operations runbook
- [ ] Update master plan
- [ ] Clean up technical debt
- [ ] Final review and sign-off

---

## 🎉 **COMPLETION CRITERIA**

Phase 3.5 is complete when:
- [ ] All infrastructure managed by Terraform
- [ ] Terraform state in S3 with locking
- [ ] CI/CD runs Terraform automatically
- [ ] Worker deploys automatically
- [ ] Zero manual AWS Console changes needed
- [ ] Documentation complete and tested
- [ ] Team trained on new workflow
- [ ] Stakeholder sign-off obtained

---

**Ready to begin Phase 3.5! This will take 3-5 days of focused work, but will provide a rock-solid foundation for all future development.** 🚀

