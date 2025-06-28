# RetainWise Analytics Infrastructure

This directory contains Terraform configuration for the RetainWise Analytics AWS infrastructure.

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** installed (version >= 1.0)
3. **AWS Account** with appropriate permissions

## Infrastructure Components

- **VPC** with public and private subnets across 2 AZs
- **S3 Bucket** for file uploads
- **ECR Repository** for Docker images
- **ECS Cluster** with Fargate tasks
- **RDS PostgreSQL** database
- **Application Load Balancer** for traffic distribution
- **IAM Roles** and policies for ECS tasks
- **Security Groups** for network security
- **CloudWatch Log Groups** for logging

## Deployment Steps

### 1. Initialize Terraform
```bash
terraform init
```

### 2. Plan the deployment
```bash
terraform plan
```

### 3. Apply the infrastructure
```bash
terraform apply -auto-approve
```

### 4. View outputs
```bash
terraform output
```

## Important Outputs

- `s3_bucket_name`: S3 bucket for uploads
- `ecr_repository_url`: ECR repository URL
- `ecs_cluster_name`: ECS cluster name
- `rds_endpoint`: RDS database endpoint
- `load_balancer_dns`: ALB DNS name

## Post-Deployment Steps

1. **Build and push Docker image**:
   ```bash
   cd ../backend
   docker build -t retainwise-backend:latest .
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(terraform output -raw ecr_repository_url)
   docker tag retainwise-backend:latest $(terraform output -raw ecr_repository_url):latest
   docker push $(terraform output -raw ecr_repository_url):latest
   ```

2. **Update ECS service** to use the new image:
   ```bash
   aws ecs update-service --cluster $(terraform output -raw ecs_cluster_name) --service retainwise-service --force-new-deployment
   ```

## Cleanup

To destroy all resources:
```bash
terraform destroy -auto-approve
```

## Security Notes

- RDS password is hardcoded in the configuration (consider using AWS Secrets Manager for production)
- Security groups are configured for basic access (review and adjust as needed)
- S3 bucket has public access blocked by default

## Cost Considerations

- RDS t3.micro: ~$15/month
- ECS Fargate (2 tasks): ~$30-50/month
- ALB: ~$20/month
- S3: Pay per use
- ECR: Pay per use

Total estimated cost: ~$65-85/month 