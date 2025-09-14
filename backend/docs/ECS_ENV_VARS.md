# ECS Environment Variables Configuration

## Required Environment Variables

The following environment variables must be set in the ECS task definition:

### Database
- **DATABASE_URL**: PostgreSQL connection string
  - Example: `postgresql+asyncpg://user:pass@host:5432/dbname`

### AWS Configuration
- **AWS_REGION**: AWS region for services
  - Example: `us-east-1`
  - Used for: SQS, S3, and other AWS services

### SQS Queue
- **PREDICTIONS_QUEUE_URL**: Full SQS queue URL for prediction jobs
  - Example: `https://sqs.us-east-1.amazonaws.com/123456789012/predictions-queue`
  - Required in production environment

### S3 Storage
- **S3_BUCKET**: S3 bucket name for file storage
  - Example: `retainwise-uploads-prod`
  - Used for: CSV uploads and prediction results

### Application
- **ENVIRONMENT**: Application environment
  - Values: `development`, `staging`, `production`
  - Default: `production` (set in Dockerfile)

## ECS Task Definition JSON Example

```json
{
  "containerDefinitions": [
    {
      "name": "retainwise-backend",
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql+asyncpg://user:pass@host:5432/dbname"
        },
        {
          "name": "AWS_REGION", 
          "value": "us-east-1"
        },
        {
          "name": "PREDICTIONS_QUEUE_URL",
          "value": "https://sqs.us-east-1.amazonaws.com/123456789012/predictions-queue"
        },
        {
          "name": "S3_BUCKET",
          "value": "retainwise-uploads-prod"
        },
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ]
    }
  ]
}
```

## IAM Permissions Required

### Backend Task Role
- **SQS Permissions:**
  - `sqs:SendMessage` to the predictions queue
  
- **S3 Permissions:**
  - `s3:GetObject` and `s3:PutObject` on the uploads bucket

### Worker Task Role (for future worker implementation)
- **SQS Permissions:**
  - `sqs:ReceiveMessage`
  - `sqs:DeleteMessage` 
  - `sqs:ChangeMessageVisibility`
  
- **S3 Permissions:**
  - `s3:GetObject` and `s3:PutObject` on the uploads bucket

## Validation

The application will validate these settings on startup:
- Log masked configuration values
- Test SQS connection in production
- Fail fast if required variables are missing in production 