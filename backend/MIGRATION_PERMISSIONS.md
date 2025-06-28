# Database Migration IAM Permissions

## Required Permissions for GitHub Actions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ExecuteCommand",
        "ecs:DescribeTasks",
        "ecs:ListTasks",
        "ecs:RunTask",
        "ecs:DescribeServices"
      ],
      "Resource": "*"
    }
  ]
}
```

## ECS Task Role Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:UpdateInstanceInformation",
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ],
      "Resource": "*"
    }
  ]
}
```

## ECS Task Definition Update

Add to task definition:
```json
{
  "enableExecuteCommand": true
}
```

## Dockerfile Update

Add SSM agent:
```dockerfile
RUN curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm" -o "session-manager-plugin.rpm" \
    && yum install -y session-manager-plugin.rpm \
    && rm session-manager-plugin.rpm
```

## Complete IAM Policy for GitHub Actions

Here's the complete policy that should be attached to the GitHub Actions IAM user:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "ecs:ExecuteCommand",
        "ecs:RunTask"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::retainwise-uploads-*",
        "arn:aws:s3:::retainwise-uploads-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

## Troubleshooting

### Common Issues

1. **Execute Command Permission Denied**:
   - Verify task role has SSM permissions
   - Check that `enableExecuteCommand` is true
   - Ensure SSM agent is installed in container

2. **Migration Script Not Found**:
   - Verify script is copied to container
   - Check file permissions
   - Ensure working directory is correct

3. **Database Connection Failed**:
   - Verify DATABASE_URL environment variable
   - Check RDS security group allows ECS tasks
   - Ensure database is accessible from VPC

### Debug Commands

```bash
# Test ECS Execute Command
aws ecs execute-command \
  --cluster retainwise-cluster \
  --task <task-arn> \
  --container retainwise-backend \
  --interactive \
  --command "/bin/bash"

# Check task logs
aws logs tail /ecs/retainwise-backend --follow

# Test database connection
aws ecs execute-command \
  --cluster retainwise-cluster \
  --task <task-arn> \
  --container retainwise-backend \
  --interactive \
  --command "/bin/bash -c 'cd /app && python -c \"import os; print(os.getenv(\"DATABASE_URL\"))\"'"
```

## Security Considerations

1. **Least Privilege**: Only grant necessary permissions
2. **Network Security**: Ensure RDS is in private subnets
3. **Secrets Management**: Use AWS Secrets Manager for database credentials
4. **Audit Logging**: Enable CloudTrail for API calls
5. **Session Logging**: Enable SSM session logging for audit trails 