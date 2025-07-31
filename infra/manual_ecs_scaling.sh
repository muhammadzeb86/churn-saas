#!/bin/bash

# Manual ECS Scaling Script for RetainWise Analytics
# Usage: ./manual_ecs_scaling.sh [up|down|status]

CLUSTER_NAME="retainwise-cluster"
SERVICE_NAME="retainwise-service"
REGION="us-east-1"

case "$1" in
    "up")
        echo "Scaling ECS service UP to 1 task..."
        aws ecs update-service \
            --cluster $CLUSTER_NAME \
            --service $SERVICE_NAME \
            --desired-count 1 \
            --region $REGION
        echo "ECS service scaled up to 1 task"
        ;;
    "down")
        echo "Scaling ECS service DOWN to 0 tasks..."
        aws ecs update-service \
            --cluster $CLUSTER_NAME \
            --service $SERVICE_NAME \
            --desired-count 0 \
            --region $REGION
        echo "ECS service scaled down to 0 tasks"
        ;;
    "status")
        echo "Current ECS service status:"
        aws ecs describe-services \
            --cluster $CLUSTER_NAME \
            --services $SERVICE_NAME \
            --region $REGION \
            --query 'services[0].{ServiceName:serviceName,DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}'
        ;;
    *)
        echo "Usage: $0 [up|down|status]"
        echo "  up     - Scale ECS service to 1 task"
        echo "  down   - Scale ECS service to 0 tasks"
        echo "  status - Show current ECS service status"
        exit 1
        ;;
esac 