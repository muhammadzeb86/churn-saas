# 🔐 Phase 3.5 Stage 3: JWT Signature Verification

**Date:** December 2, 2025  
**Priority:** P0 - CRITICAL SECURITY  
**Status:** IN PROGRESS  
**Estimated Time:** 3 hours  
**Approach:** Option B - Enable + Enhance Existing Code

---

## 📋 **EXECUTIVE SUMMARY**

### **What We Found:**
✅ **Good News:** JWT verification code already exists and is production-ready!
- `backend/auth/jwt_verifier.py`: 382 lines of high-quality code
- `backend/auth/middleware.py`: 3-tier authentication strategy
- JWKS client with caching, async locking, graceful degradation

❌ **Bad News:** It's disabled in production
- Environment variables not set
- Using insecure fallback mode
- No test coverage (0%)
- Unsafe bypass mechanism exists

### **Security Impact:**
🚨 **CRITICAL:** Anyone can forge JWT tokens without signature verification

### **Solution:**
1. ✅ Enable existing implementation (30 min) - **IN PROGRESS**
2. Remove unsafe fallback (1 hour)
3. Add comprehensive tests (1 hour)
4. Add monitoring (30 min)

---

## 🎯 **TASK 3.1: ENABLE JWT VERIFICATION (IN PROGRESS)**

### **Step 1: Find Your Clerk Domain**

**You need to provide:**
```
CLERK_FRONTEND_API=<your-clerk-domain>
```

**How to find it:**
1. Go to https://dashboard.clerk.com
2. Select your application
3. Go to **API Keys** section
4. Look for **"Frontend API"** - copy the domain part

**Format examples:**
- Custom domain: `clerk.retainwiseanalytics.com`
- Clerk subdomain: `adapted-tern-12.clerk.accounts.dev`

⚠️ **Important:** Just the domain, NO `https://` prefix!

---

### **Step 2: Update ECS Task Definitions**

Once you provide the Clerk domain, I'll update:

**Backend Task Definition:**
```json
{
  "environment": [
    {
      "name": "CLERK_FRONTEND_API",
      "value": "<your-clerk-domain>"
    },
    {
      "name": "JWT_SIGNATURE_VERIFICATION_ENABLED",
      "value": "true"
    }
  ]
}
```

**Worker Task Definition:**
```json
{
  "environment": [
    {
      "name": "CLERK_FRONTEND_API",
      "value": "<your-clerk-domain>"
    },
    {
      "name": "JWT_SIGNATURE_VERIFICATION_ENABLED",
      "value": "true"
    }
  ]
}
```

---

### **Step 3: Deploy**

```bash
# Backend will be at revision 94
# Worker will force-redeploy with same task definition

# Both services will restart with new env vars
# JWT verification will activate automatically
```

---

### **Step 4: Verify**

**Test CSV Upload:**
1. Go to https://app.retainwiseanalytics.com
2. Upload a CSV file
3. Should work without 401 errors

**Check Logs:**
```bash
# Should see this instead of warning:
INFO: ✅ JWT signature verified successfully for user: user_xxx

# Should NOT see this:
WARNING: ⚠️ FALLBACK: Authenticated user via structure check only
```

---

## 📝 **TASK 3.2: REMOVE UNSAFE FALLBACK**

### **Why This Matters:**
Security principle: **Never ship bypass mechanisms to production**

### **Code Changes:**

#### **File: `backend/auth/middleware.py`**

**Change 1:** Delete fallback function (lines 248-296)
```python
# DELETE ENTIRE FUNCTION
async def _authenticate_production_fallback(token: str) -> Dict:
    # ... 48 lines ...
```

**Change 2:** Simplify main function (lines 89-136)
```python
async def get_current_user(credentials):
    if AUTH_DEV_MODE:
        return await _authenticate_dev_mode(token)
    
    # Always use verified authentication in production
    return await _authenticate_production_verified(token)
```

**Change 3:** Remove feature flag (line 29-32)
```python
# DELETE THIS TOGGLE
JWT_SIGNATURE_VERIFICATION_ENABLED = ...
```

**Impact:**
- 50 lines of code removed
- No more security bypass
- Simpler, more secure code

---

## 🧪 **TASK 3.3: ADD COMPREHENSIVE TESTS**

### **New File: `backend/tests/test_auth_verification.py`**

**Test Coverage:**
- JWKS client (cache, fetch, errors)
- JWT verification (valid, invalid, expired)
- Middleware integration (auth flow, errors)

**Target Metrics:**
- Line coverage: >95%
- Branch coverage: >90%
- Execution time: <5 seconds

**Why This Matters:**
- Prevents regressions
- Documents expected behavior
- Builds confidence

---

## 📊 **TASK 3.4: ADD MONITORING**

### **Metrics to Track:**
```python
{
  "jwt_verifications_success": 1250,
  "jwt_verifications_failure": 15,
  "jwks_cache_hits": 1240,
  "jwks_cache_misses": 25,
  "jwks_fetch_errors": 0
}
```

### **CloudWatch Alarms:**
- High 401 rate (>10%)
- JWKS unavailable (>3 errors in 5min)
- Any 503 errors (CRITICAL)

---

## ✅ **SUCCESS CRITERIA**

### **Stage 3 Complete When:**
- [x] Codebase audited - **DONE**
- [x] Roadmap updated - **DONE**
- [ ] Clerk domain provided
- [ ] Environment variables set
- [ ] Services redeployed
- [ ] CSV upload tested
- [ ] Warning gone from logs
- [ ] Fallback code removed
- [ ] Tests added (>95% coverage)
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Committed and pushed

---

## 🚀 **NEXT ACTIONS**

### **For You:**
1. **Find your Clerk domain**
   - Go to Clerk dashboard
   - Copy Frontend API domain
   - Share with me

### **For Me (Once You Provide Domain):**
1. Update task definitions with env vars
2. Deploy both services
3. Test CSV upload
4. Remove fallback code
5. Add comprehensive tests
6. Add monitoring
7. Update documentation
8. Commit and push

---

## 📞 **QUESTIONS?**

### **Q: Will this break existing users?**
A: No - users will just need to re-login (normal behavior)

### **Q: What if Clerk is down?**
A: Graceful degradation - uses cached keys for up to 24 hours

### **Q: Performance impact?**
A: <5ms per request (signature verification is fast)

### **Q: Can we roll back?**
A: Yes - 3 minute rollback via ECS task definition

### **Q: Why not just leave the fallback?**
A: Security principle - never ship bypass mechanisms

---

## 📚 **REFERENCES**

- **Codebase Audit:** This chat
- **Roadmap:** `PHASE_3.5_INFRASTRUCTURE_ROADMAP.md` (Stage 3)
- **Existing Code:** `backend/auth/jwt_verifier.py`, `backend/auth/middleware.py`
- **JWT Standard:** RFC 7519
- **JWKS Standard:** RFC 7517

---

**Status:** ⏳ **WAITING ON CLERK DOMAIN FROM USER**

Once you provide your Clerk domain, I'll proceed with implementation! 🚀

