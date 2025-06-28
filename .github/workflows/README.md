# GitHub Actions CI/CD Setup

This directory contains GitHub Actions workflows for automated deployment of the RetainWise Analytics backend.

## Workflows

### `backend-ci-cd.yml`

Automated CI/CD pipeline that:
1. **Builds and tests** the backend application
2. **Builds Docker image** and pushes to ECR
3. **Deploys infrastructure** (if Terraform files changed)
4. **Updates ECS service** with new image
5. **Performs health checks** on the deployed application

## Required GitHub Secrets

You must configure these secrets in your GitHub repository settings:

### AWS Credentials
- `AWS_ACCESS_KEY_ID`: Your AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key

### How to Set Up AWS Credentials

1. **Create IAM User** (if you don't have one):
   ```bash
   aws iam create-user --user-name github-actions
   ```

2. **Attach Required Policies**:
   ```bash
   # Attach policies for ECR, ECS, and other services
   aws iam attach-user-policy --user-name github-actions --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
   aws iam attach-user-policy --user-name github-actions --policy-arn arn:aws:iam::aws:policy/AmazonECS-FullAccess
   aws iam attach-user-policy --user-name github-actions --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
   aws iam attach-user-policy --user-name github-actions --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
   aws iam attach-user-policy --user-name github-actions --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
   ```

3. **Create Access Keys**:
   ```bash
   aws iam create-access-key --user-name github-actions
   ```

4. **Add to GitHub Secrets**:
   - Go to your GitHub repository
   - Settings → Secrets and variables → Actions
   - Add the access key ID and secret access key

## Workflow Triggers

The workflow runs on:
- **Push to main branch** (with changes to backend/, infra/, or workflow files)
- **Pull requests to main branch** (build and test only, no deployment)

## Workflow Jobs

### 1. Build and Test
- Sets up Python environment
- Installs dependencies
- Builds Docker image
- Tests image locally

### 2. Deploy (main branch only)
- Logs into AWS ECR
- Pushes Docker image to ECR
- Checks for infrastructure changes
- Runs Terraform if needed
- Updates ECS task definition
- Forces ECS service redeployment
- Waits for service stabilization

### 3. Health Check (main branch only)
- Waits for application to be ready
- Tests health endpoint
- Reports deployment status

## Environment Variables

The workflow uses these environment variables:
- `AWS_REGION`: us-east-1
- `ECR_REPOSITORY`: retainwise-backend
- `ECS_CLUSTER`: retainwise-cluster
- `ECS_SERVICE`: retainwise-service
- `ECS_TASK_DEFINITION`: retainwise-backend

## Manual Deployment

To manually trigger a deployment:
1. Go to Actions tab in GitHub
2. Select "Backend CI/CD Pipeline"
3. Click "Run workflow"
4. Select branch and click "Run workflow"

## Troubleshooting

### Common Issues

1. **AWS Credentials Error**:
   - Verify secrets are correctly set in GitHub
   - Check IAM user has required permissions

2. **ECR Login Failed**:
   - Ensure ECR repository exists
   - Check AWS region matches repository location

3. **ECS Service Update Failed**:
   - Verify cluster and service names
   - Check task definition is valid

4. **Terraform Apply Failed**:
   - Check Terraform state is consistent
   - Verify AWS credentials have Terraform permissions

### Debugging

- Check workflow logs in GitHub Actions
- Use `aws ecs describe-services` to check service status
- Check CloudWatch logs for application errors 