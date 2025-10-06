import json
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ecs = boto3.client('ecs')
ssm = boto3.client('ssm')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    EventBridge guardrail to detect and auto-correct task definition drift
    """
    try:
        # Get the golden task definition from SSM Parameter Store
        golden_td_param = ssm.get_parameter(
            Name='/retainwise/golden-task-definition'
        )
        golden_td_arn = golden_td_param['Parameter']['Value']
        
        # Get current service task definition
        service_response = ecs.describe_services(
            cluster='retainwise-cluster',
            services=['retainwise-service']
        )
        
        if not service_response['services']:
            logger.error("Service not found")
            return {'statusCode': 500, 'body': 'Service not found'}
        
        current_td_arn = service_response['services'][0]['taskDefinition']
        
        # Check for drift
        if current_td_arn != golden_td_arn:
            logger.warning(f"Task definition drift detected!")
            logger.warning(f"Current: {current_td_arn}")
            logger.warning(f"Golden: {golden_td_arn}")
            
            # Send alert
            send_drift_alert(current_td_arn, golden_td_arn)
            
            # Auto-correct by updating service to golden TD
            auto_correct_drift(golden_td_arn)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Drift detected and corrected',
                    'current_td': current_td_arn,
                    'golden_td': golden_td_arn
                })
            }
        else:
            logger.info("No drift detected - service is using golden task definition")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No drift detected',
                    'task_definition': current_td_arn
                })
            }
            
    except Exception as e:
        logger.error(f"Error in guardrail: {str(e)}")
        return {'statusCode': 500, 'body': f'Error: {str(e)}'}

def send_drift_alert(current_td, golden_td):
    """Send SNS alert about task definition drift"""
    try:
        message = f"""
         TASK DEFINITION DRIFT DETECTED 
        
        Service: retainwise-service
        Cluster: retainwise-cluster
        Time: {datetime.now().isoformat()}
        
        Current TD: {current_td}
        Golden TD: {golden_td}
        
        Action: Auto-correcting to golden task definition...
        """
        
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:908226940571:retainwise-alerts',
            Subject='ECS Task Definition Drift Alert',
            Message=message
        )
        logger.info("Drift alert sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send drift alert: {str(e)}")

def auto_correct_drift(golden_td_arn):
    """Auto-correct drift by updating service to golden task definition"""
    try:
        ecs.update_service(
            cluster='retainwise-cluster',
            service='retainwise-service',
            taskDefinition=golden_td_arn,
            forceNewDeployment=True
        )
        logger.info(f"Service updated to golden task definition: {golden_td_arn}")
        
    except Exception as e:
        logger.error(f"Failed to auto-correct drift: {str(e)}")
        raise
