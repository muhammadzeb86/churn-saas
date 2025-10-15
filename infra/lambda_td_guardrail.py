import json
import boto3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ecs = boto3.client('ecs')
ssm = boto3.client('ssm')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    EventBridge guardrail to detect task definition drift and send alerts
    ALERT-ONLY MODE: Does NOT auto-correct drift to avoid conflicts with CI/CD
    """
    try:
        # Get the golden task definition from SSM Parameter Store
        golden_td_param = ssm.get_parameter(
            Name='/retainwise/golden-task-definition'
        )
        golden_td_arn = golden_td_param['Parameter']['Value']
        golden_td_updated = golden_td_param['Parameter']['LastModifiedDate']
        
        # Get current service task definition
        service_response = ecs.describe_services(
            cluster='retainwise-cluster',
            services=['retainwise-service']
        )
        
        if not service_response['services']:
            logger.error("Service not found")
            return {'statusCode': 500, 'body': 'Service not found'}
        
        service = service_response['services'][0]
        current_td_arn = service['taskDefinition']
        
        # Get deployment information to check if there's an active deployment
        deployments = service.get('deployments', [])
        active_deployment = len(deployments) > 1  # More than 1 deployment means deployment in progress
        
        # Check for drift
        if current_td_arn != golden_td_arn:
            logger.warning(f"Task definition drift detected!")
            logger.warning(f"Current: {current_td_arn}")
            logger.warning(f"Golden: {golden_td_arn}")
            logger.warning(f"Golden TD last updated: {golden_td_updated}")
            logger.warning(f"Active deployment in progress: {active_deployment}")
            
            # Calculate how long the drift has existed
            time_since_golden_update = datetime.now(golden_td_updated.tzinfo) - golden_td_updated
            
            # Only alert if drift has existed for more than 15 minutes AND no active deployment
            if time_since_golden_update > timedelta(minutes=15) and not active_deployment:
                logger.error("GENUINE DRIFT DETECTED - drift persisted for >15 minutes with no active deployment")
                send_drift_alert(current_td_arn, golden_td_arn, time_since_golden_update)
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Drift detected - alert sent (no auto-correction)',
                        'current_td': current_td_arn,
                        'golden_td': golden_td_arn,
                        'drift_duration_minutes': time_since_golden_update.total_seconds() / 60,
                        'action': 'alert_only'
                    })
                }
            else:
                logger.info(f"Drift detected but within grace period ({time_since_golden_update.total_seconds()/60:.1f} minutes) or deployment in progress - no alert")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Drift detected but within acceptable parameters',
                        'current_td': current_td_arn,
                        'golden_td': golden_td_arn,
                        'drift_duration_minutes': time_since_golden_update.total_seconds() / 60,
                        'active_deployment': active_deployment,
                        'action': 'monitoring'
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

def send_drift_alert(current_td, golden_td, drift_duration):
    """Send SNS alert about task definition drift"""
    try:
        message = f"""
⚠️ TASK DEFINITION DRIFT DETECTED ⚠️

Service: retainwise-service
Cluster: retainwise-cluster
Time: {datetime.now().isoformat()}
Drift Duration: {drift_duration.total_seconds() / 60:.1f} minutes

Current TD: {current_td}
Golden TD: {golden_td}

⚠️ ACTION REQUIRED: Manual investigation needed
This guardrail is in ALERT-ONLY mode and will NOT auto-correct.

Possible causes:
1. Manual intervention via AWS Console
2. Unauthorized deployment
3. Golden TD parameter not updated by CI/CD

To resolve:
1. Check recent deployments in GitHub Actions
2. Verify Golden TD parameter in SSM is correct
3. If legitimate deployment, update Golden TD parameter
4. If unauthorized, investigate and revert
        """
        
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:908226940571:retainwise-alerts',
            Subject='⚠️ ECS Task Definition Drift Alert - Manual Investigation Required',
            Message=message
        )
        logger.info("Drift alert sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send drift alert: {str(e)}")
