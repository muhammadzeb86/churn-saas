# S3 Integration Deployment Guide

This document outlines the deployment steps for the S3 file upload integration in RetainWise Analytics.

## Overview

The backend now uses S3 for all file storage instead of local disk. This provides:
- Scalable storage
- No local disk space limitations
- Better security and access control
- Integration with AWS services

## Required Environment Variables

Add these environment variables to your deployment:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
S3_BUCKET=retainwise-uploads-your-account-id
```

## ECS Task Definition Updates

### 1. Add Environment Variables

Update your ECS task definition to include the S3 environment variables:

```json
{
  "environment": [
    {
      "name": "AWS_REGION",
      "value": "us-east-1"
    },
    {
      "name": "S3_BUCKET",
      "value": "retainwise-uploads-your-account-id"
    }
  ]
}
```

### 2. Add IAM Role Permissions

Ensure your ECS task role has S3 permissions. Add this policy to your task role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::retainwise-uploads-your-account-id",
        "arn:aws:s3:::retainwise-uploads-your-account-id/*"
      ]
    }
  ]
}
```

## New API Endpoints

### 1. Direct Upload Endpoint
```
POST /upload/csv
Content-Type: multipart/form-data

Parameters:
- file: CSV file
- user_id: User ID (integer)
```

### 2. Presigned URL Endpoint
```
POST /upload/presign
Content-Type: application/x-www-form-urlencoded

Parameters:
- filename: File name
- user_id: User ID (integer)
```

### 3. Confirm Upload Endpoint
```
POST /upload/confirm-upload
Content-Type: application/x-www-form-urlencoded

Parameters:
- object_key: S3 object key
- user_id: User ID (integer)
- filename: Original filename
- file_size: File size in bytes (optional)
```

### 4. List User Uploads
```
GET /upload/files/{user_id}
```

## Database Migration

The Upload model has been updated with new fields:
- `s3_object_key`: S3 object key for the file
- `file_size`: File size in bytes

Run database migration to add these columns:

```sql
-- Add new columns to uploads table
ALTER TABLE uploads ADD COLUMN s3_object_key TEXT NOT NULL;
ALTER TABLE uploads ADD COLUMN file_size INTEGER;

-- Update existing records (if any)
UPDATE uploads SET s3_object_key = CONCAT('uploads/', user_id, '/', filename) WHERE s3_object_key IS NULL;
```

## Deployment Steps

### 1. Update Environment Variables
- Add AWS credentials to ECS task definition
- Set S3_BUCKET environment variable

### 2. Update IAM Permissions
- Add S3 permissions to ECS task role
- Ensure bucket access is properly configured

### 3. Deploy Updated Code
- Build and push new Docker image with boto3
- Update ECS service

### 4. Test Upload Functionality
- Test direct upload endpoint
- Test presigned URL generation
- Verify files are stored in S3

## Security Considerations

1. **IAM Roles**: Use IAM roles instead of access keys when possible
2. **Bucket Policies**: Configure S3 bucket policies for access control
3. **CORS**: Configure CORS on S3 bucket if needed for client-side uploads
4. **Encryption**: Enable server-side encryption on S3 bucket

## Monitoring

Monitor the following:
- S3 upload success/failure rates
- File sizes and upload times
- S3 storage costs
- Application logs for upload errors

## Troubleshooting

### Common Issues

1. **AWS Credentials Error**:
   - Verify environment variables are set
   - Check IAM role permissions

2. **S3 Upload Failed**:
   - Verify bucket name is correct
   - Check bucket permissions
   - Ensure bucket exists

3. **Database Migration Issues**:
   - Run migration SQL manually if needed
   - Check database connection

### Debug Commands

```bash
# Check ECS task environment variables
aws ecs describe-task-definition --task-definition retainwise-backend

# Check S3 bucket contents
aws s3 ls s3://retainwise-uploads-your-account-id/uploads/

# Check application logs
aws logs tail /ecs/retainwise-backend --follow
``` 