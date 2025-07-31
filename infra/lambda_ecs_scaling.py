import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda function to scale ECS service up or down based on schedule
    """
    # ECS client
    ecs = boto3.client('ecs')
    
    # Get ECS cluster and service names from environment variables
    cluster_name = os.environ['ECS_CLUSTER_NAME']
    service_name = os.environ['ECS_SERVICE_NAME']
    
    # Get desired count from event
    desired_count = event.get('desired_count', 1)
    
    try:
        # Update ECS service
        response = ecs.update_service(
            cluster=cluster_name,
            service=service_name,
            desiredCount=desired_count
        )
        
        print(f"Successfully updated ECS service {service_name} to {desired_count} tasks")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'ECS service {service_name} scaled to {desired_count} tasks',
                'cluster': cluster_name,
                'service': service_name,
                'desired_count': desired_count,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error updating ECS service: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to scale ECS service: {str(e)}',
                'cluster': cluster_name,
                'service': service_name,
                'desired_count': desired_count
            })
        } 