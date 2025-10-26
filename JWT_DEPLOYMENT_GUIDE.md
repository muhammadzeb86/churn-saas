# 🔐 JWT Signature Verification - Production Deployment Guide

## 📋 Overview

This guide covers the deployment of production-grade JWT signature verification for Clerk authentication. The implementation includes:

- ✅ Full RS256 signature verification with JWKS
- ✅ JWKS caching with 24-hour TTL
- ✅ Graceful degradation on Clerk service issues
- ✅ Feature flag for phased rollout (zero-downtime deployment)
- ✅ Development mode for local testing
- ✅ Comprehensive logging and error handling

---

## 🎯 Deployment Strategy: Phased Rollout

We use a **phased rollout** approach for zero-downtime, zero-risk deployment:

```
Phase 1: Deploy code with feature flag OFF
         └─> Old authentication continues (no risk)
         
Phase 2: Enable feature flag via ECS environment variable
         └─> New JWT verification activates
         
Phase 3: Monitor for 24-48 hours
         └─> Verify no errors
         
Phase 4: Remove feature flag (make permanent)
         └─> Clean up fallback code
```

---

## 🚀 PRE-DEPLOYMENT: Local Validation (10 minutes)

### Step 1: Get Your Clerk Domain

1. Go to https://dashboard.clerk.com
2. Select your application
3. Go to **API Keys** section
4. Find **"Frontend API"** - it will show something like:
   - `https://adapted-tern-12.clerk.accounts.dev`
   - Copy just the domain: `adapted-tern-12.clerk.accounts.dev`
   
   **OR** if you have a custom domain:
   - `https://clerk.yourapp.com`
   - Copy: `clerk.yourapp.com`

### Step 2: Set Environment Variable Locally

```bash
# On Windows PowerShell:
$env:CLERK_FRONTEND_API="adapted-tern-12.clerk.accounts.dev"

# On Windows CMD:
set CLERK_FRONTEND_API=adapted-tern-12.clerk.accounts.dev

# On Linux/Mac:
export CLERK_FRONTEND_API=adapted-tern-12.clerk.accounts.dev
```

### Step 3: Run Local Validation

```bash
# From project root
cd c:\Projects\churn-saas

# Activate virtual environment
.\venv\Scripts\activate

# Run validation script
python test_jwt_locally.py
```

**Expected Output:**
```
============================================================
        JWT Verification Local Test Suite
============================================================

✅ CLERK_FRONTEND_API is set: adapted-tern-12.clerk.accounts.dev
✅ JWT verifier module imported successfully
✅ JWT verifier initialized successfully
✅ JWKS fetched successfully
   Number of keys: 2
   Key 1: kid=ins_2X..., kty=RSA, use=sig, alg=RS256

============================================================
                    TEST SUMMARY
============================================================
✅ ALL TESTS PASSED ✅

Your JWT verification setup is ready for deployment!
```

**If tests FAIL:**
- Check Clerk domain is correct
- Verify internet connection
- Ensure dependencies installed (`pip install python-jose[cryptography] httpx`)

---

## 📦 DEPLOYMENT PHASE 1: Deploy with Feature Flag OFF (15 minutes)

### Step 1: Commit Changes

```bash
git add backend/auth/jwt_verifier.py
git add backend/auth/middleware.py
git add backend/main.py
git add test_jwt_locally.py
git add JWT_DEPLOYMENT_GUIDE.md

git commit -m "feat: add production JWT signature verification with phased rollout

- Implement RS256 signature verification with Clerk JWKS
- Add JWKS caching with 24-hour TTL and graceful degradation
- Add feature flag JWT_SIGNATURE_VERIFICATION_ENABLED for safe rollout
- Add startup self-test for authentication system
- Add local validation script
- Maintain backward compatibility and dev mode"

git push origin main
```

### Step 2: GitHub Actions Will Deploy Automatically

Monitor the deployment:
```bash
# Watch GitHub Actions
# https://github.com/YOUR-REPO/actions
```

### Step 3: Verify Deployment

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --region us-east-1 \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,taskDef:taskDefinition}'

# Wait for runningCount == desiredCount
```

### Step 4: Check CloudWatch Logs

```bash
# Tail logs to see startup
aws logs tail /ecs/retainwise-backend --follow --since 5m --region us-east-1
```

**Look for these log messages:**
```
✅ JWT Verifier initialized for domain: adapted-tern-12.clerk.accounts.dev
⚠️  Production mode but signature verification is DISABLED:
   - JWT_SIGNATURE_VERIFICATION_ENABLED=false
```

This confirms:
- ✅ Code deployed successfully
- ✅ JWT verifier initialized (but not active)
- ✅ Old authentication still working

---

## 🔄 DEPLOYMENT PHASE 2: Enable JWT Verification (5 minutes)

### Step 1: Update ECS Environment Variables

**Option A: Via AWS Console**

1. Go to ECS Console → Clusters → `retainwise-cluster`
2. Click on `retainwise-service`
3. Click **Update** button
4. Click **Revision** tab
5. Click **Create new revision**
6. Scroll to **Environment variables**
7. Add/Update these variables:
   ```
   CLERK_FRONTEND_API = adapted-tern-12.clerk.accounts.dev
   JWT_SIGNATURE_VERIFICATION_ENABLED = true
   AUTH_DEV_MODE = false
   ```
8. Click **Create**
9. Back on service page, click **Update Service**
10. Select the new task definition revision
11. Click **Update**

**Option B: Via AWS CLI** (Recommended)

```bash
# First, get current task definition
aws ecs describe-task-definition \
  --task-definition retainwise-backend \
  --region us-east-1 \
  > current-task-def.json

# Edit current-task-def.json to add environment variables in containerDefinitions[0].environment:
# {
#   "name": "CLERK_FRONTEND_API",
#   "value": "adapted-tern-12.clerk.accounts.dev"
# },
# {
#   "name": "JWT_SIGNATURE_VERIFICATION_ENABLED",
#   "value": "true"
# },
# {
#   "name": "AUTH_DEV_MODE",
#   "value": "false"
# }

# Register new task definition
aws ecs register-task-definition \
  --cli-input-json file://current-task-def.json \
  --region us-east-1

# Update service to use new task definition
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment \
  --region us-east-1
```

### Step 2: Wait for New Tasks to Start (3-5 minutes)

```bash
# Watch service status
aws ecs describe-services \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --region us-east-1 \
  --query 'services[0].events[0:5]'
```

### Step 3: Verify JWT Verification is Active

```bash
# Tail logs
aws logs tail /ecs/retainwise-backend --follow --since 2m --region us-east-1
```

**Look for these log messages:**
```
✅ JWT Verifier initialized for domain: adapted-tern-12.clerk.accounts.dev
✅ JWKS fetched successfully: 2 keys available
✅ Production authentication mode ACTIVE:
   - JWT signature verification: ENABLED
   - JWKS validation: ENABLED
   - Security: MAXIMUM
✅ Authentication system self-test PASSED
```

---

## 🧪 TESTING IN PRODUCTION (15 minutes)

### Test 1: Login to Application

1. Go to https://app.retainwiseanalytics.com
2. Login with your Clerk account
3. Verify you can access dashboard
4. Check browser console for errors

### Test 2: Upload CSV

1. Navigate to Upload page
2. Upload a CSV file
3. Verify upload succeeds
4. Check CloudWatch logs:

```bash
aws logs tail /ecs/retainwise-backend --since 5m --region us-east-1 | grep "JWT"
```

**Expected log output:**
```
✅ JWT signature verified successfully for user: user_2X...
✅ Production authentication successful for user user_2X... (signature VERIFIED)
```

### Test 3: Check Predictions

1. Navigate to Predictions page
2. Verify you can see your predictions
3. Download a prediction result
4. All should work normally

### Test 4: Monitor Error Rates

```bash
# Check for JWT verification errors
aws logs tail /ecs/retainwise-backend --since 30m --region us-east-1 | grep -i "error"

# Check ALB 5xx errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value=app/retainwise-alb/... \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1
```

---

## 🚨 ROLLBACK PROCEDURE (If Issues Occur)

If you encounter authentication errors after enabling JWT verification:

### IMMEDIATE ROLLBACK (1 minute)

**Option 1: Disable Feature Flag via Console**

1. Go to ECS → `retainwise-cluster` → `retainwise-service`
2. Update → Create new revision
3. Change `JWT_SIGNATURE_VERIFICATION_ENABLED` to `false`
4. Update service with new revision

**Option 2: Disable Feature Flag via CLI**

```bash
# Quick rollback command
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment \
  --region us-east-1

# Then manually update task definition to set:
# JWT_SIGNATURE_VERIFICATION_ENABLED=false
```

### Verify Rollback

```bash
aws logs tail /ecs/retainwise-backend --follow --since 2m --region us-east-1
```

**Look for:**
```
⚠️ Production mode but signature verification is DISABLED
⚠️ FALLBACK: Authenticated user via structure check only
```

Users should be able to login again within 1-2 minutes.

---

## 📊 MONITORING (24-48 hours)

### Key Metrics to Watch

**1. Authentication Success Rate**
```bash
# Count successful JWT verifications
aws logs filter-pattern "JWT signature verified successfully" \
  --log-group-name /ecs/retainwise-backend \
  --start-time $(($(date +%s) - 3600))000 \
  --region us-east-1
```

**2. Authentication Errors**
```bash
# Count JWT verification failures
aws logs filter-pattern "JWT verification failed" \
  --log-group-name /ecs/retainwise-backend \
  --start-time $(($(date +%s) - 3600))000 \
  --region us-east-1
```

**3. JWKS Cache Performance**
```bash
# Check JWKS fetch frequency (should be ~once per 24 hours)
aws logs filter-pattern "Fetching JWKS from" \
  --log-group-name /ecs/retainwise-backend \
  --start-time $(($(date +%s) - 86400))000 \
  --region us-east-1
```

**4. API Response Times**
```bash
# Check if JWT verification added latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value=app/retainwise-alb/... \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --region us-east-1
```

### Success Criteria

After 24-48 hours, verify:
- ✅ No increase in 401/403 errors
- ✅ Authentication success rate > 99%
- ✅ No JWKS fetch failures
- ✅ API response time unchanged (< 500ms)
- ✅ No user complaints about login issues

---

## ✅ DEPLOYMENT PHASE 3: Make Permanent (After 24-48 hours)

Once monitoring confirms everything is stable:

### Remove Feature Flag (Optional)

You can keep the feature flag for future flexibility, or remove it:

```python
# backend/auth/middleware.py
# Remove this check:
if JWT_SIGNATURE_VERIFICATION_ENABLED:
    return await _authenticate_production_verified(token)

# Keep only:
return await _authenticate_production_verified(token)
```

### Update Documentation

Update internal docs to reflect:
- JWT signature verification is now mandatory in production
- `AUTH_DEV_MODE=true` only for local development
- Clerk domain configuration is required

---

## 🔧 TROUBLESHOOTING

### Issue: "CLERK_FRONTEND_API environment variable required"

**Cause**: Environment variable not set in ECS task definition

**Fix**:
```bash
# Verify environment variables
aws ecs describe-task-definition \
  --task-definition retainwise-backend \
  --query 'taskDefinition.containerDefinitions[0].environment' \
  --region us-east-1

# Should show CLERK_FRONTEND_API
```

### Issue: "Signing key not found for kid"

**Cause**: JWKS keys rotated, cache is stale

**Fix**:
```bash
# Restart ECS tasks to clear cache
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment \
  --region us-east-1
```

### Issue: "Token has expired"

**Cause**: User's session expired (normal behavior)

**Fix**: User needs to re-login. This is expected and not an error.

### Issue: High latency after deployment

**Cause**: JWKS fetch on first request

**Expected**: First request after restart takes ~100-200ms extra
**Normal**: Subsequent requests use cached JWKS (< 10ms overhead)

### Issue: "Authentication service temporarily unavailable"

**Cause**: Cannot reach Clerk's JWKS endpoint

**Check**:
1. ECS tasks have internet access (public IPs or NAT Gateway)
2. Security groups allow outbound HTTPS (port 443)
3. Clerk service is operational (check status.clerk.com)

---

## 📞 SUPPORT

If you encounter issues during deployment:

1. **Check CloudWatch Logs** first
2. **Run rollback procedure** to restore service
3. **Review this guide** for troubleshooting steps
4. **Re-run local validation** to verify configuration

---

## 📈 SUCCESS METRICS

**Security Improvements:**
- ✅ JWT signatures now cryptographically verified
- ✅ Protection against forged tokens
- ✅ Proper issuer validation
- ✅ Expiration time enforcement

**Operational Improvements:**
- ✅ Zero downtime deployment
- ✅ Instant rollback capability
- ✅ Graceful degradation on Clerk issues
- ✅ Comprehensive logging for debugging

**Performance:**
- ✅ JWKS cached for 24 hours (minimal overhead)
- ✅ No added latency on cached requests
- ✅ Async operations prevent blocking

---

**🎉 Congratulations! Your JWT verification is now production-secure.**

