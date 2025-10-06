#!/bin/bash

# RetainWise Deployment Script
# This script helps with manual deployments and testing of the new infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="us-east-1"
ECS_CLUSTER="retainwise-cluster"
ECS_SERVICE="retainwise-service"
ECS_TASK_DEFINITION="retainwise-backend"
GOLDEN_TD_PARAM="/retainwise/golden-task-definition"

echo -e "${BLUE}🚀 RetainWise Deployment Script${NC}"
echo "=================================="

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or credentials are invalid"
        exit 1
    fi
    
    print_status "AWS CLI is configured"
}

# Function to get current service status
get_service_status() {
    print_info "Getting current service status..."
    
    aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --query 'services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount,TaskDefinition:taskDefinition}' \
        --output table
}

# Function to get current task definition
get_current_task_definition() {
    CURRENT_TD=$(aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --query 'services[0].taskDefinition' \
        --output text)
    
    echo $CURRENT_TD
}

# Function to get golden task definition
get_golden_task_definition() {
    GOLDEN_TD=$(aws ssm get-parameter \
        --name $GOLDEN_TD_PARAM \
        --query 'Parameter.Value' \
        --output text)
    
    echo $GOLDEN_TD
}

# Function to update golden task definition
update_golden_task_definition() {
    local new_td_arn=$1
    
    print_info "Updating Golden Task Definition to: $new_td_arn"
    
    aws ssm put-parameter \
        --name $GOLDEN_TD_PARAM \
        --value "$new_td_arn" \
        --overwrite \
        --description "Golden task definition ARN - authoritative source of truth for production deployments"
    
    print_status "Golden Task Definition updated successfully!"
}

# Function to test version endpoint
test_version_endpoint() {
    print_info "Testing version endpoint..."
    
    # Get ALB DNS name
    ALB_DNS=$(aws elbv2 describe-load-balancers \
        --query 'LoadBalancers[?contains(LoadBalancerName, `retainwise`)].DNSName' \
        --output text)
    
    if [ -z "$ALB_DNS" ]; then
        print_error "Could not find load balancer DNS name"
        return 1
    fi
    
    print_info "Testing version endpoint at: https://$ALB_DNS/__version"
    
    VERSION_RESPONSE=$(curl -s https://$ALB_DNS/__version)
    
    if [ $? -eq 0 ]; then
        print_status "Version endpoint is accessible"
        echo "Response: $VERSION_RESPONSE"
        
        # Check if response contains expected fields
        if echo "$VERSION_RESPONSE" | jq -e '.commit_sha, .build_time, .deployment_id' > /dev/null; then
            print_status "Version endpoint contains all expected fields"
        else
            print_warning "Version endpoint missing some expected fields"
        fi
    else
        print_error "Version endpoint is not accessible"
        return 1
    fi
}

# Function to test guardrails
test_guardrails() {
    print_info "Testing guardrails system..."
    
    # Get current and golden task definitions
    CURRENT_TD=$(get_current_task_definition)
    GOLDEN_TD=$(get_golden_task_definition)
    
    print_info "Current Task Definition: $CURRENT_TD"
    print_info "Golden Task Definition: $GOLDEN_TD"
    
    if [ "$CURRENT_TD" = "$GOLDEN_TD" ]; then
        print_status "No drift detected - service is using golden task definition"
    else
        print_warning "Drift detected! Current TD differs from Golden TD"
        print_info "The Lambda guardrail should auto-correct this within 5 minutes"
    fi
}

# Function to manually trigger guardrail
trigger_guardrail() {
    print_info "Manually triggering guardrail Lambda function..."
    
    aws lambda invoke \
        --function-name retainwise-td-guardrail \
        --payload '{}' \
        --cli-binary-format raw-in-base64-out \
        /tmp/guardrail-response.json
    
    if [ $? -eq 0 ]; then
        print_status "Guardrail triggered successfully"
        cat /tmp/guardrail-response.json | jq .
    else
        print_error "Failed to trigger guardrail"
    fi
}

# Function to show deployment summary
show_deployment_summary() {
    echo ""
    echo -e "${BLUE}📊 Deployment Summary${NC}"
    echo "====================="
    
    # Service status
    echo -e "\n${BLUE}Service Status:${NC}"
    get_service_status
    
    # Task definitions
    echo -e "\n${BLUE}Task Definitions:${NC}"
    CURRENT_TD=$(get_current_task_definition)
    GOLDEN_TD=$(get_golden_task_definition)
    echo "Current:  $CURRENT_TD"
    echo "Golden:   $GOLDEN_TD"
    
    # Version endpoint
    echo -e "\n${BLUE}Version Endpoint:${NC}"
    if test_version_endpoint; then
        print_status "Version endpoint is working"
    else
        print_error "Version endpoint has issues"
    fi
    
    # Guardrails
    echo -e "\n${BLUE}Guardrails:${NC}"
    test_guardrails
}

# Main menu
show_menu() {
    echo ""
    echo "Select an option:"
    echo "1. Show deployment summary"
    echo "2. Test version endpoint"
    echo "3. Test guardrails"
    echo "4. Update golden task definition"
    echo "5. Trigger guardrail manually"
    echo "6. Get service status"
    echo "7. Exit"
    echo ""
}

# Main script logic
main() {
    check_aws_cli
    
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Enter your choice (1-7): " choice
            
            case $choice in
                1)
                    show_deployment_summary
                    ;;
                2)
                    test_version_endpoint
                    ;;
                3)
                    test_guardrails
                    ;;
                4)
                    CURRENT_TD=$(get_current_task_definition)
                    update_golden_task_definition "$CURRENT_TD"
                    ;;
                5)
                    trigger_guardrail
                    ;;
                6)
                    get_service_status
                    ;;
                7)
                    print_status "Goodbye!"
                    exit 0
                    ;;
                *)
                    print_error "Invalid option. Please try again."
                    ;;
            esac
        done
    else
        # Command line mode
        case $1 in
            "summary")
                show_deployment_summary
                ;;
            "test-version")
                test_version_endpoint
                ;;
            "test-guardrails")
                test_guardrails
                ;;
            "update-golden")
                CURRENT_TD=$(get_current_task_definition)
                update_golden_task_definition "$CURRENT_TD"
                ;;
            "trigger-guardrail")
                trigger_guardrail
                ;;
            "status")
                get_service_status
                ;;
            *)
                echo "Usage: $0 [summary|test-version|test-guardrails|update-golden|trigger-guardrail|status]"
                exit 1
                ;;
        esac
    fi
}

# Run main function
main "$@"
