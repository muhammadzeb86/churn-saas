# Backend Deployment and Migration

## Automated Deployment with GitHub Actions

This project is configured for automated deployment to AWS ECS using GitHub Actions. The workflow is defined in `.github/workflows/deploy.yml`.

### Workflow Triggers

The deployment workflow is automatically triggered on any push to the `main` branch that includes changes in the `backend/` directory.

### Workflow Steps

1.  **Checkout Code**: The latest code from the `main` branch is checked out.
2.  **Configure AWS Credentials**: AWS credentials are set up using secrets stored in GitHub.
3.  **Login to ECR**: The workflow logs into the Amazon ECR registry.
4.  **Build and Push Docker Image**: The backend Docker image is built, tagged as `latest`, and pushed to ECR.
5.  **Run Database Migrations**: A one-off ECS task is run to execute the database migrations using the `backend/scripts/run_migrations.py` script. The workflow waits for this task to complete before proceeding.
6.  **Update ECS Service**: The ECS service is updated with the new Docker image, triggering a new deployment of the backend application.

### Required Secrets

The following secrets must be configured in the GitHub repository for the workflow to run successfully:

*   `AWS_ACCESS_KEY_ID`: The access key for an IAM user with permissions to ECR, ECS, and other required services.
*   `AWS_SECRET_ACCESS_KEY`: The secret key for the IAM user.
*   `SUBNET_ID_1`: The ID of the first public subnet for the ECS task.
*   `SUBNET_ID_2`: The ID of the second public subnet for the ECS task.
*   `SECURITY_GROUP_ID`: The ID of the security group for the ECS task.

## Manual Deployment

While the automated workflow is recommended, you can also deploy the backend manually.

### 1. Build and Push the Docker Image

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build the image
docker build -t retainwise-backend:latest ./backend

# Tag the image
docker tag retainwise-backend:latest <your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com/retainwise-backend:latest

# Push the image
docker push <your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com/retainwise-backend:latest
```

### 2. Run Database Migrations

```bash
aws ecs run-task \
  --cluster retainwise-cluster \
  --task-definition retainwise-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<your-subnet-id-1>, <your-subnet-id-2>],securityGroups=[<your-security-group-id>],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"retainwise-backend","command":["python","backend/scripts/run_migrations.py"]}]}' \
  --wait 'tasksStopped'
```

### 3. Update the ECS Service

```bash
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --task-definition retainwise-backend \
  --force-new-deployment
``` 