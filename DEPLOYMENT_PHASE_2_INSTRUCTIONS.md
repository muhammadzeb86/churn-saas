# 🚀 DEPLOYMENT PHASE 2: Enable JWT Signature Verification

## Current Status

✅ **Phase 1 Complete**: Code deployed with JWT verification DISABLED (feature flag OFF)
⚠️ **Phase 2 Required**: Enable JWT signature verification

---

## 🎯 What You Need to Do (5 minutes)

### Step 1: Open ECS Console

Go to: https://console.aws.amazon.com/ecs/v2/clusters/retainwise-cluster/services/retainwise-service

### Step 2: Click "Update Service"

Click the **"Update"** button (top right corner)

### Step 3: Update Task Definition

1. Click **"Create new revision"** under Task Definition
2. Scroll down to **"Environment variables"** section
3. Click **"Add environment variable"** THREE times to add:

   **Variable 1:**
   - Name: `CLERK_FRONTEND_API`
   - Value: `clerk.retainwiseanalytics.com`
   
   **Variable 2:**
   - Name: `JWT_SIGNATURE_VERIFICATION_ENABLED`
   - Value: `true`
   
   **Variable 3:**
   - Name: `AUTH_DEV_MODE`
   - Value: `false`

4. Click **"Create"**

### Step 4: Update Service

1. You'll be returned to the "Update Service" page
2. **Do NOT change the task definition** (it's already the new one)
3. Just click **"Update Service"** button at the bottom
4. Confirm the update

### Step 5: Wait for Deployment (3-5 minutes)

The service will:
1. Register new task definition revision
2. Start new tasks with JWT verification enabled
3. Drain connections from old tasks
4. Stop old tasks

**Monitor progress:**
```bash
aws ecs describe-services --cluster retainwise-cluster --service retainwise-service --region us-east-1 --query 'services[0].events[0:10]'
```

### Step 6: Verify JWT Verification is Active

**Watch CloudWatch logs:**
```bash
aws logs tail /ecs/retainwise-backend --follow --since 2m --region us-east-1
```

**Look for these messages:**
```
✅ JWT Verifier initialized for domain: clerk.retainwiseanalytics.com
✅ Production authentication mode ACTIVE:
   - JWT signature verification: ENABLED
   - JWKS validation: ENABLED
✅ JWKS fetched successfully: X keys available
✅ Authentication system self-test PASSED
```

If you see these messages, **SUCCESS!** ✅

---

## 🧪 Testing (10 minutes)

### Test 1: Login
1. Go to https://app.retainwiseanalytics.com
2. Login with your Clerk account
3. Should work normally

### Test 2: Upload CSV
1. Navigate to Upload page
2. Upload a CSV file
3. Should succeed

### Test 3: Check Logs for Verification
```bash
aws logs tail /ecs/retainwise-backend --since 5m --region us-east-1 | grep "JWT signature verified"
```

**Expected output:**
```
✅ JWT signature verified successfully for user: user_2X...
```

---

## 🚨 ROLLBACK (If Issues Occur)

If you see authentication errors:

1. **Go to ECS Console**
2. **Update Service**
3. **Change** `JWT_SIGNATURE_VERIFICATION_ENABLED` to `false`
4. **Update Service**

This will restore old authentication within 1-2 minutes.

---

## 📊 SUCCESS INDICATORS

After 15 minutes, verify:

- ✅ Login works
- ✅ CSV upload works
- ✅ Predictions page loads
- ✅ CloudWatch logs show "signature VERIFIED" messages
- ✅ No 401/403 authentication errors

---

## 📝 NEXT STEPS (After Verification)

1. Monitor for 24-48 hours
2. Check CloudWatch logs daily
3. After 48 hours of stable operation, consider removing feature flag
4. Document final state

---

**Total time: 15 minutes active work + 48 hours monitoring**

