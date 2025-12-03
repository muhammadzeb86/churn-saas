# ⚡ JWT Verification - Quick Deploy Checklist

## ✅ PRE-DEPLOYMENT (10 min)

- [x] **Get Clerk domain** from dashboard.clerk.com → API Keys → Frontend API
  ```
  Domain: clerk.retainwiseanalytics.com
  ```

- [x] **Run local test**
  ```bash
  $env:CLERK_FRONTEND_API="clerk.retainwiseanalytics.com"
  python test_jwt_locally.py
  ```
  
- [x] **Verify test passes** (all ✅ green checks) - **COMPLETED**

---

## 🚀 DEPLOYMENT PHASE 1: Deploy Code (15 min)

- [x] **Commit and push** - **COMPLETED** (commit: f65fa64)
  ```bash
  git add backend/auth/ backend/main.py test_jwt_locally.py
  git commit -m "feat: add JWT signature verification"
  git push origin main
  ```

- [x] **Watch GitHub Actions** complete - **COMPLETED**

- [x] **Verify ECS deployment** - **COMPLETED** (task def: 62)
  ```bash
  aws ecs describe-services --cluster retainwise-cluster --service retainwise-service --region us-east-1
  ```

- [x] **Check logs for startup messages** - **COMPLETED**
  ```bash
  aws logs tail /ecs/retainwise-backend --follow --since 5m --region us-east-1
  ```
  Found: ⚠️ "signature verification is DISABLED" (feature flag OFF)

---

## 🔄 DEPLOYMENT PHASE 2: Enable Verification (5 min)

- [x] **Update ECS environment variables** - **COMPLETED**
  ```
  CLERK_FRONTEND_API = clerk.retainwiseanalytics.com
  JWT_SIGNATURE_VERIFICATION_ENABLED = true
  AUTH_DEV_MODE = false
  ```

- [x] **Create new task definition** - **COMPLETED** (task def: 63)

- [x] **Update service with new task definition** - **COMPLETED**

- [x] **Check logs for activation** - **COMPLETED**
  ```bash
  aws logs tail /ecs/retainwise-backend --follow --since 2m --region us-east-1
  ```
  Found: ✅ "JWT Verifier initialized", ✅ "JWKS fetched successfully", ✅ "Self-test PASSED"

---

## 🧪 TESTING (15 min)

- [ ] **Test login** at app.retainwiseanalytics.com
- [ ] **Upload a CSV** and verify it works
- [ ] **Check predictions** page
- [ ] **Review logs** for JWT verification success messages
  ```bash
  aws logs tail /ecs/retainwise-backend --since 5m --region us-east-1 | grep "JWT signature verified"
  ```

---

## 📊 MONITORING (24-48 hours)

- [ ] **Day 1: Check every 4 hours**
  - No authentication errors
  - Login still works
  - API response times normal

- [ ] **Day 2: Check twice**
  - Verify JWKS caching working (only 1-2 fetches per day)
  - No user complaints

---

## 🚨 ROLLBACK (If needed)

**IMMEDIATE: Set feature flag to false**
```bash
# Update task definition:
JWT_SIGNATURE_VERIFICATION_ENABLED = false

# Force redeployment
aws ecs update-service --cluster retainwise-cluster --service retainwise-service --force-new-deployment --region us-east-1
```

---

## ✅ COMPLETION (After 48 hours)

- [ ] **Verify all metrics green**
  - Auth success rate > 99%
  - No JWKS fetch failures
  - API latency unchanged

- [ ] **Document final state**
  - JWT verification: ENABLED ✅
  - JWKS caching: ACTIVE ✅
  - Security: MAXIMUM ✅

- [ ] **Optional: Remove feature flag code** (can keep for flexibility)

---

## 📞 Quick Troubleshoot Commands

```bash
# View recent logs
aws logs tail /ecs/retainwise-backend --since 30m --region us-east-1

# Check service status
aws ecs describe-services --cluster retainwise-cluster --service retainwise-service --region us-east-1

# Count auth errors (last hour)
aws logs filter-pattern "JWT verification failed" --log-group-name /ecs/retainwise-backend --start-time $(($(date +%s) - 3600))000 --region us-east-1

# Force task restart
aws ecs update-service --cluster retainwise-cluster --service retainwise-service --force-new-deployment --region us-east-1
```

---

**🎯 Total Time: ~30 minutes active work + 48 hours monitoring**

**📖 For detailed steps, see: JWT_DEPLOYMENT_GUIDE.md**

