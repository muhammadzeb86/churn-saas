# RetainWise Deployment Script (PowerShell)
# This script helps with manual deployments and testing of the new infrastructure

param(
    [Parameter(Position=0)]
    [string]$Action = "menu"
)

# Configuration
$AWS_REGION = "us-east-1"
$ECS_CLUSTER = "retainwise-cluster"
$ECS_SERVICE = "retainwise-service"
$ECS_TASK_DEFINITION = "retainwise-backend"
$GOLDEN_TD_PARAM = "/retainwise/golden-task-definition"

Write-Host "🚀 RetainWise Deployment Script" -ForegroundColor Blue
Write-Host "==================================" -ForegroundColor Blue

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Cyan
}

# Function to check if AWS CLI is configured
function Test-AWSCLI {
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Error "AWS CLI is not installed"
        exit 1
    }
    
    try {
        aws sts get-caller-identity | Out-Null
        Write-Status "AWS CLI is configured"
    }
    catch {
        Write-Error "AWS CLI is not configured or credentials are invalid"
        exit 1
    }
}

# Function to get current service status
function Get-ServiceStatus {
    Write-Info "Getting current service status..."
    
    aws ecs describe-services `
        --cluster $ECS_CLUSTER `
        --services $ECS_SERVICE `
        --query 'services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount,TaskDefinition:taskDefinition}' `
        --output table
}

# Function to get current task definition
function Get-CurrentTaskDefinition {
    $currentTd = aws ecs describe-services `
        --cluster $ECS_CLUSTER `
        --services $ECS_SERVICE `
        --query 'services[0].taskDefinition' `
        --output text
    
    return $currentTd.Trim()
}

# Function to get golden task definition
function Get-GoldenTaskDefinition {
    $goldenTd = aws ssm get-parameter `
        --name $GOLDEN_TD_PARAM `
        --query 'Parameter.Value' `
        --output text
    
    return $goldenTd.Trim()
}

# Function to update golden task definition
function Update-GoldenTaskDefinition {
    param([string]$NewTdArn)
    
    Write-Info "Updating Golden Task Definition to: $NewTdArn"
    
    aws ssm put-parameter `
        --name $GOLDEN_TD_PARAM `
        --value $NewTdArn `
        --overwrite `
        --description "Golden task definition ARN - authoritative source of truth for production deployments"
    
    Write-Status "Golden Task Definition updated successfully!"
}

# Function to test version endpoint
function Test-VersionEndpoint {
    Write-Info "Testing version endpoint..."
    
    # Get ALB DNS name
    $albDns = aws elbv2 describe-load-balancers `
        --query 'LoadBalancers[?contains(LoadBalancerName, `retainwise`)].DNSName' `
        --output text
    
    if ([string]::IsNullOrWhiteSpace($albDns)) {
        Write-Error "Could not find load balancer DNS name"
        return $false
    }
    
    Write-Info "Testing version endpoint at: https://$albDns/__version"
    
    try {
        $response = Invoke-RestMethod -Uri "https://$albDns/__version" -Method Get
        Write-Status "Version endpoint is accessible"
        Write-Host "Response: $($response | ConvertTo-Json -Depth 3)"
        
        # Check if response contains expected fields
        if ($response.commit_sha -and $response.build_time -and $response.deployment_id) {
            Write-Status "Version endpoint contains all expected fields"
            return $true
        }
        else {
            Write-Warning "Version endpoint missing some expected fields"
            return $false
        }
    }
    catch {
        Write-Error "Version endpoint is not accessible: $($_.Exception.Message)"
        return $false
    }
}

# Function to test guardrails
function Test-Guardrails {
    Write-Info "Testing guardrails system..."
    
    # Get current and golden task definitions
    $currentTd = Get-CurrentTaskDefinition
    $goldenTd = Get-GoldenTaskDefinition
    
    Write-Info "Current Task Definition: $currentTd"
    Write-Info "Golden Task Definition: $goldenTd"
    
    if ($currentTd -eq $goldenTd) {
        Write-Status "No drift detected - service is using golden task definition"
    }
    else {
        Write-Warning "Drift detected! Current TD differs from Golden TD"
        Write-Info "The Lambda guardrail should auto-correct this within 5 minutes"
    }
}

# Function to manually trigger guardrail
function Invoke-Guardrail {
    Write-Info "Manually triggering guardrail Lambda function..."
    
    try {
        $response = aws lambda invoke `
            --function-name retainwise-td-guardrail `
            --payload '{}' `
            --cli-binary-format raw-in-base64-out `
            /tmp/guardrail-response.json
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Guardrail triggered successfully"
            $content = Get-Content /tmp/guardrail-response.json -Raw
            Write-Host $content
        }
        else {
            Write-Error "Failed to trigger guardrail"
        }
    }
    catch {
        Write-Error "Error triggering guardrail: $($_.Exception.Message)"
    }
}

# Function to show deployment summary
function Show-DeploymentSummary {
    Write-Host ""
    Write-Host "📊 Deployment Summary" -ForegroundColor Blue
    Write-Host "=====================" -ForegroundColor Blue
    
    # Service status
    Write-Host "`nService Status:" -ForegroundColor Blue
    Get-ServiceStatus
    
    # Task definitions
    Write-Host "`nTask Definitions:" -ForegroundColor Blue
    $currentTd = Get-CurrentTaskDefinition
    $goldenTd = Get-GoldenTaskDefinition
    Write-Host "Current:  $currentTd"
    Write-Host "Golden:   $goldenTd"
    
    # Version endpoint
    Write-Host "`nVersion Endpoint:" -ForegroundColor Blue
    if (Test-VersionEndpoint) {
        Write-Status "Version endpoint is working"
    }
    else {
        Write-Error "Version endpoint has issues"
    }
    
    # Guardrails
    Write-Host "`nGuardrails:" -ForegroundColor Blue
    Test-Guardrails
}

# Function to show menu
function Show-Menu {
    Write-Host ""
    Write-Host "Select an option:"
    Write-Host "1. Show deployment summary"
    Write-Host "2. Test version endpoint"
    Write-Host "3. Test guardrails"
    Write-Host "4. Update golden task definition"
    Write-Host "5. Trigger guardrail manually"
    Write-Host "6. Get service status"
    Write-Host "7. Exit"
    Write-Host ""
}

# Main script logic
function Main {
    Test-AWSCLI
    
    if ($Action -eq "menu") {
        # Interactive mode
        do {
            Show-Menu
            $choice = Read-Host "Enter your choice (1-7)"
            
            switch ($choice) {
                "1" { Show-DeploymentSummary }
                "2" { Test-VersionEndpoint }
                "3" { Test-Guardrails }
                "4" { 
                    $currentTd = Get-CurrentTaskDefinition
                    Update-GoldenTaskDefinition $currentTd
                }
                "5" { Invoke-Guardrail }
                "6" { Get-ServiceStatus }
                "7" { 
                    Write-Status "Goodbye!"
                    exit 0
                }
                default { Write-Error "Invalid option. Please try again." }
            }
        } while ($true)
    }
    else {
        # Command line mode
        switch ($Action) {
            "summary" { Show-DeploymentSummary }
            "test-version" { Test-VersionEndpoint }
            "test-guardrails" { Test-Guardrails }
            "update-golden" { 
                $currentTd = Get-CurrentTaskDefinition
                Update-GoldenTaskDefinition $currentTd
            }
            "trigger-guardrail" { Invoke-Guardrail }
            "status" { Get-ServiceStatus }
            default { 
                Write-Host "Usage: .\deploy.ps1 [summary|test-version|test-guardrails|update-golden|trigger-guardrail|status]"
                exit 1
            }
        }
    }
}

# Run main function
Main
