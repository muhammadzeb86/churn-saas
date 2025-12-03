# Fix SQS Environment Variables in Backend Task Definition
# This script manually adds PREDICTIONS_QUEUE_URL and ENABLE_SQS to the backend

$ErrorActionPreference = "Stop"

Write-Host "=" -ForegroundColor Blue -NoNewline
Write-Host ("=" * 59) -ForegroundColor Blue
Write-Host "🔧 FIXING SQS ENVIRONMENT VARIABLES" -ForegroundColor Blue
Write-Host "=" -ForegroundColor Blue -NoNewline
Write-Host ("=" * 59) -ForegroundColor Blue
Write-Host ""

# Configuration
$CLUSTER = "retainwise-cluster"
$SERVICE = "retainwise-service"
$TASK_DEF = "retainwise-backend"
$QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue"
$REGION = "us-east-1"

Write-Host "📥 Step 1: Downloading current task definition..." -ForegroundColor Cyan
aws ecs describe-task-definition `
    --task-definition $TASK_DEF `
    --region $REGION `
    --query 'taskDefinition' > task-def-current.json

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to download task definition" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Task definition downloaded" -ForegroundColor Green
Write-Host ""

Write-Host "🔍 Step 2: Checking current environment variables..." -ForegroundColor Cyan
$currentEnvVars = aws ecs describe-task-definition `
    --task-definition $TASK_DEF `
    --region $REGION `
    --query 'taskDefinition.containerDefinitions[0].environment[?name==`PREDICTIONS_QUEUE_URL` || name==`ENABLE_SQS`]' `
    --output json | ConvertFrom-Json

if ($currentEnvVars.Count -eq 0) {
    Write-Host "⚠️  No SQS environment variables found (expected)" -ForegroundColor Yellow
} else {
    Write-Host "ℹ️  Found $($currentEnvVars.Count) SQS environment variables" -ForegroundColor Blue
}
Write-Host ""

Write-Host "➕ Step 3: Adding SQS environment variables..." -ForegroundColor Cyan
$jqCommand = @"
.containerDefinitions[0].environment += [
  {\"name\": \"PREDICTIONS_QUEUE_URL\", \"value\": \"$QUEUE_URL\"},
  {\"name\": \"ENABLE_SQS\", \"value\": \"true\"}
] | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
"@

# Use jq to add environment variables and remove AWS-managed fields
$jqCommand | Set-Content -Path jq-command.txt
Get-Content task-def-current.json | jq -f jq-command.txt > task-def-updated.json

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to update task definition JSON" -ForegroundColor Red
    Write-Host "Make sure jq is installed: https://stedolan.github.io/jq/download/" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ SQS environment variables added" -ForegroundColor Green
Write-Host ""

Write-Host "📝 Step 4: Registering new task definition..." -ForegroundColor Cyan
$registerOutput = aws ecs register-task-definition `
    --cli-input-json file://task-def-updated.json `
    --region $REGION | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to register task definition" -ForegroundColor Red
    exit 1
}

$newRevision = $registerOutput.taskDefinition.revision
Write-Host "✅ New task definition registered: $TASK_DEF`:$newRevision" -ForegroundColor Green
Write-Host ""

Write-Host "🚀 Step 5: Forcing service update..." -ForegroundColor Cyan
aws ecs update-service `
    --cluster $CLUSTER `
    --service $SERVICE `
    --force-new-deployment `
    --region $REGION | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to update service" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Service update triggered" -ForegroundColor Green
Write-Host ""

Write-Host "⏳ Step 6: Waiting for service to stabilize..." -ForegroundColor Cyan
Write-Host "This may take 2-3 minutes..." -ForegroundColor Yellow
aws ecs wait services-stable `
    --cluster $CLUSTER `
    --services $SERVICE `
    --region $REGION

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Service didn't stabilize in time, but deployment is in progress" -ForegroundColor Yellow
} else {
    Write-Host "✅ Service stabilized successfully!" -ForegroundColor Green
}
Write-Host ""

Write-Host "🔍 Step 7: Verifying SQS environment variables..." -ForegroundColor Cyan
$verifyEnvVars = aws ecs describe-task-definition `
    --task-definition "$TASK_DEF`:$newRevision" `
    --region $REGION `
    --query 'taskDefinition.containerDefinitions[0].environment[?name==`PREDICTIONS_QUEUE_URL` || name==`ENABLE_SQS`]' `
    --output json | ConvertFrom-Json

if ($verifyEnvVars.Count -eq 2) {
    Write-Host "✅ SQS environment variables verified:" -ForegroundColor Green
    foreach ($var in $verifyEnvVars) {
        if ($var.name -eq "PREDICTIONS_QUEUE_URL") {
            $maskedUrl = $var.value -replace '(https://sqs[^/]+/[^/]+/)', '$1***/'
            Write-Host "  - $($var.name): $maskedUrl" -ForegroundColor White
        } else {
            Write-Host "  - $($var.name): $($var.value)" -ForegroundColor White
        }
    }
} else {
    Write-Host "❌ SQS environment variables not found!" -ForegroundColor Red
}
Write-Host ""

Write-Host "🧹 Step 8: Cleaning up temporary files..." -ForegroundColor Cyan
Remove-Item -Path task-def-current.json, task-def-updated.json, jq-command.txt -ErrorAction SilentlyContinue
Write-Host "✅ Cleanup complete" -ForegroundColor Green
Write-Host ""

Write-Host "=" -ForegroundColor Blue -NoNewline
Write-Host ("=" * 59) -ForegroundColor Blue
Write-Host "✅ FIX COMPLETE!" -ForegroundColor Green
Write-Host "=" -ForegroundColor Blue -NoNewline
Write-Host ("=" * 59) -ForegroundColor Blue
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Wait 2-3 minutes for new task to start" -ForegroundColor White
Write-Host "2. Check logs: aws logs tail /ecs/retainwise-backend --follow --region us-east-1" -ForegroundColor White
Write-Host "3. Look for: '✅ SQS client initialized'" -ForegroundColor White
Write-Host "4. No more 'SQS not configured' messages" -ForegroundColor White
Write-Host ""
Write-Host "Monitor deployment:" -ForegroundColor Cyan
Write-Host "aws ecs describe-services --cluster $CLUSTER --services $SERVICE --query 'services[0].{Running:runningCount,Desired:desiredCount,TaskDef:taskDefinition}' --region $REGION" -ForegroundColor White

