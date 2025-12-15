# 🚀 **PRE-LAUNCH CHECKLIST FOR RETAINWISE**

**Last Updated:** December 15, 2025  
**Version:** 1.0  
**Target Launch Date:** [TBD]

---

## **📋 CRITICAL - MUST COMPLETE BEFORE LAUNCH**

### **1. ⚠️ Enable Redis for Prediction Caching** 

**Status:** ❌ **NOT DEPLOYED** (currently gracefully disabled)

**Why Critical:**
- **Cost Savings:** 30-50% compute cost reduction
- **Performance:** <10ms cache hits vs 850ms full predictions
- **User Experience:** Faster results for repeat uploads
- **ROI:** $30-50/month savings vs $15/month cost = **positive ROI**

**Setup Options:**

#### **Option A: AWS ElastiCache (Recommended for Production)**
```bash
# 1. Create ElastiCache Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id retainwise-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --region us-east-1 \
  --tags Key=Project,Value=RetainWise Key=Environment,Value=Production

# 2. Get endpoint after creation (~10 minutes)
aws elasticache describe-cache-clusters \
  --cache-cluster-id retainwise-cache \
  --show-cache-node-info \
  --region us-east-1 \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint'

# Expected output: 
# {
#   "Address": "retainwise-cache.abc123.0001.use1.cache.amazonaws.com",
#   "Port": 6379
# }

# 3. Update ECS Task Definition environment variables
# REDIS_URL=redis://retainwise-cache.abc123.0001.use1.cache.amazonaws.com:6379

# 4. Redeploy ECS services
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --force-new-deployment \
  --region us-east-1

aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment \
  --region us-east-1
```

**Cost:** $15/month (cache.t3.micro)

#### **Option B: Redis Cloud (Alternative)**
- Sign up: https://redis.com/try-free/
- Free tier: 30MB (good for testing)
- Paid tier: $10/month for 100MB
- Get connection URL and set as `REDIS_URL` environment variable

**Verification:**
```bash
# Check logs for successful Redis connection
aws logs tail /ecs/retainwise-worker --follow --since 5m | grep "cache_connected"

# Expected: "cache_connected" with redis_url shown
```

---

### **2. ☁️ Deploy CloudWatch Dashboard**

**Status:** ❌ **NOT DEPLOYED**

**Why Important:**
- Real-time monitoring of production system
- Proactive alerting before users report issues
- Performance regression detection
- Cost tracking and budget alerts

**Cost:** 
- Dashboard: **FREE** (up to 3 dashboards)
- Custom metrics: **$0.30/metric/month** × 10 metrics = **$3/month**
- CloudWatch Insights queries: ~**$5/month**
- **Total: $8/month**

**Deployment:**
```bash
# Run from project root
cd /path/to/churn-saas
python -m backend.monitoring.cloudwatch_dashboard --deploy
```

**View Dashboard After Deployment:**
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=RetainWise-Production

**What You'll See:**
- 📊 Predictions per hour
- 🚨 Error rate %
- ⏱️ P95 latency
- 💰 Daily cost estimate
- 📈 Performance trends
- 🔥 Recent failures
- 🔒 Security events

---

### **3. 🔒 Review & Tighten IAM Permissions**

**Status:** ⚠️ **NEEDS REVIEW**

**Why Critical:**
- Prevent $20M+ GDPR fines
- Protect against data breaches
- Follow principle of least privilege

**Action Items:**

#### **A. Audit ECS Task Roles**
```bash
# Run IAM auditor
python -c "
from backend.core.security import iam_auditor
result = iam_auditor.audit_task_role_permissions('ecsTaskExecutionRole')
print(result)
"
```

**Expected Violations to Fix:**
- ❌ `s3:*` (too broad) → Use `s3:GetObject`, `s3:PutObject` only
- ❌ `s3:DeleteBucket` (dangerous) → Remove entirely
- ❌ Wildcard resource `*` → Specify bucket ARNs

#### **B. Correct IAM Policy Example**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::retainwise-predictions/*",
        "arn:aws:s3:::retainwise-uploads/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage"
      ],
      "Resource": "arn:aws:sqs:us-east-1:*:retainwise-predictions"
    }
  ]
}
```

---

### **4. 🔐 Enable MFA Delete on S3 Buckets**

**Status:** ❌ **NOT ENABLED**

**Why Critical:**
- Prevent accidental bucket deletion
- Requires multi-factor authentication for delete operations
- Protects against compromised credentials

**Setup:**
```bash
# Enable MFA Delete (requires root account MFA)
aws s3api put-bucket-versioning \
  --bucket retainwise-predictions \
  --versioning-configuration Status=Enabled,MFADelete=Enabled \
  --mfa "arn:aws:iam::123456789:mfa/root-account-mfa-device XXXXXX" \
  --region us-east-1
```

---

### **5. ✅ Enable S3 Bucket Versioning** 

**Status:** ✅ **LIKELY ALREADY ENABLED** (verify below)

**Verification:**
```bash
aws s3api get-bucket-versioning \
  --bucket retainwise-predictions \
  --region us-east-1

# Expected: {"Status": "Enabled"}
```

**If not enabled:**
```bash
aws s3api put-bucket-versioning \
  --bucket retainwise-predictions \
  --versioning-configuration Status=Enabled \
  --region us-east-1
```

---

### **6. 📊 Set Up CloudWatch Alarms**

**Status:** ❌ **NOT DEPLOYED**

**Why Critical:**
- Get notified BEFORE users complain
- Proactive incident response
- Automated alerting to on-call engineer

**Deploy Alarms:**
```bash
python -m backend.monitoring.cloudwatch_dashboard --deploy
# This creates both dashboard AND alarms
```

**Alarms Created:**
1. **High Error Rate** (>5% in 5 minutes) → SNS notification
2. **High Latency** (P95 >1000ms) → SNS notification
3. **Daily Cost Exceeded** (>$10/day) → SNS notification

**TODO:** Configure SNS topic for email/SMS notifications
```bash
# Create SNS topic
aws sns create-topic --name retainwise-production-alerts --region us-east-1

# Subscribe to email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789:retainwise-production-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1

# Confirm subscription via email
```

---

### **7. 🔄 Test Disaster Recovery Procedures**

**Status:** ❌ **NOT TESTED**

**Why Important:**
- Verify RTO/RPO targets are achievable
- Team knows what to do during outage
- Find gaps in runbook before real incident

**Test Scenarios:**

#### **A. Database Restore Drill (Staging)**
```bash
# 1. Create test snapshot
aws rds create-db-snapshot \
  --db-instance-identifier retainwise-db-staging \
  --db-snapshot-identifier test-restore-$(date +%Y%m%d) \
  --region us-east-1

# 2. Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier retainwise-db-restored-test \
  --db-snapshot-identifier test-restore-20251215 \
  --db-instance-class db.t3.micro \
  --region us-east-1

# 3. Wait and verify
aws rds wait db-instance-available \
  --db-instance-identifier retainwise-db-restored-test \
  --region us-east-1

# 4. Cleanup
aws rds delete-db-instance \
  --db-instance-identifier retainwise-db-restored-test \
  --skip-final-snapshot \
  --region us-east-1
```

**Record Results:**
- Time to restore: ______ minutes (Target: <30 minutes)
- Data loss: ______ (Target: <1 hour)
- Issues encountered: ______

#### **B. S3 File Recovery Drill**
```bash
# 1. Delete a test file
aws s3 rm s3://retainwise-predictions/test/sample.csv

# 2. List versions
aws s3api list-object-versions \
  --bucket retainwise-predictions \
  --prefix "test/sample.csv"

# 3. Restore
aws s3api copy-object \
  --bucket retainwise-predictions \
  --copy-source "retainwise-predictions/test/sample.csv?versionId=VERSION_ID" \
  --key "test/sample.csv"

# 4. Verify restoration
aws s3 ls s3://retainwise-predictions/test/sample.csv
```

---

### **8. 📝 Update Status Page**

**Status:** ⚠️ **NEEDS SETUP**

**Options:**

#### **Option A: StatusPage.io (Recommended)**
- Cost: $29/month
- URL: https://status.retainwise.ai
- Features: Incident management, uptime monitoring, subscriber notifications

#### **Option B: Atlassian Statuspage**
- Cost: $29/month
- Similar features to StatusPage.io

#### **Option C: Open Source (Cachet)**
- Cost: Free (hosting costs only)
- Self-hosted
- More setup work

**What to Monitor:**
- API availability (https://api.retainwise.ai/health)
- Prediction processing (SQS queue depth)
- Database connectivity
- S3 upload/download

---

## **🎯 RECOMMENDED - BEFORE FULL LAUNCH**

### **9. 🧪 Load Testing**

**Status:** ❌ **NOT DONE**

**Why Recommended:**
- Verify system handles expected load
- Find bottlenecks before customers do
- Validate auto-scaling works

**Test Scenarios:**

#### **Scenario 1: Burst Load (100 predictions/hour)**
```python
# load_test.py
import concurrent.futures
import requests

def upload_prediction(i):
    with open('test_saas_customers_100.csv', 'rb') as f:
        response = requests.post(
            'https://api.retainwise.ai/upload',
            files={'file': f},
            headers={'Authorization': f'Bearer {token}'}
        )
    return response.status_code

# Upload 100 files in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(upload_prediction, range(100)))

print(f"Success rate: {results.count(200)}/100")
```

**Expected Results:**
- ✅ Success rate: >95%
- ✅ P95 latency: <1000ms
- ✅ Error rate: <5%
- ✅ Auto-scaling triggers if needed

#### **Scenario 2: Sustained Load (50 predictions/hour for 4 hours)**
Run above script with 50 concurrent uploads every hour for 4 hours.

**Monitor:**
- CloudWatch dashboard during test
- ECS CPU/memory usage
- RDS connection count
- S3 PUT request rate

---

### **10. 💰 Set AWS Budget Alerts**

**Status:** ❌ **NOT CONFIGURED**

**Setup:**
```bash
# Create budget (via AWS Console or CLI)
# Budget: $300/month
# Alert thresholds: 50%, 80%, 100%
# Notification: Email + SMS
```

**Expected Monthly Costs (500 customers):**
- ECS Fargate: $40-60/month
- RDS (db.t3.micro): $12/month
- S3 storage + requests: $10-20/month
- ElastiCache Redis: $15/month
- CloudWatch: $8/month
- **Total: ~$85-115/month**

**Growth Buffer:** Set budget at $300/month (3x expected)

---

### **11. 📧 Set Up Transactional Email (SendGrid/SES)**

**Status:** ⚠️ **CHECK IF CONFIGURED**

**Why Needed:**
- Send prediction completion emails
- Error notifications to users
- Password reset emails (Clerk handles this)

**If using AWS SES:**
```bash
# Move out of sandbox (required for production)
# Request: https://console.aws.amazon.com/ses/home#/account
# Approval takes 1-2 business days
```

---

### **12. 🔍 Enable AWS CloudTrail**

**Status:** ⚠️ **LIKELY ENABLED BY DEFAULT**

**Why Important:**
- Audit trail for all AWS API calls
- Required for compliance (SOC 2, GDPR)
- Forensics for security incidents

**Verification:**
```bash
aws cloudtrail describe-trails --region us-east-1

# Expected: At least one trail enabled
```

**Cost:** ~$2/month for trail + S3 storage

---

## **🎉 NICE-TO-HAVE (Post-Launch)**

### **13. 🌍 Multi-Region Failover**

**Status:** ❌ **NOT CONFIGURED** (acceptable for MVP)

**When to implement:** Revenue > $50K/month

**Setup:**
- RDS cross-region read replica (us-west-2)
- S3 cross-region replication
- Route53 failover routing

**Cost:** ~$100/month additional

---

### **14. 🔐 WAF (Web Application Firewall)**

**Status:** ❌ **NOT CONFIGURED** (acceptable for MVP)

**When to implement:** After first security incident or at 1000+ users

**Cost:** $5/month + $1 per million requests

---

### **15. 📊 Advanced Analytics (Mixpanel/Amplitude)**

**Status:** ❌ **NOT CONFIGURED**

**Why Useful:**
- User behavior tracking
- Conversion funnel analysis
- Feature usage analytics

**Cost:** Free tier available, then $25-100/month

---

## **✅ LAUNCH READINESS CHECKLIST**

**Before you launch, complete this checklist:**

- [ ] **Redis caching enabled** (ElastiCache or Redis Cloud)
- [ ] **CloudWatch dashboard deployed**
- [ ] **CloudWatch alarms configured with SNS notifications**
- [ ] **IAM permissions audited and tightened**
- [ ] **S3 MFA Delete enabled**
- [ ] **S3 versioning verified**
- [ ] **Disaster recovery procedures tested** (at least database restore)
- [ ] **Status page set up** (https://status.retainwise.ai)
- [ ] **Load testing completed** (100 predictions/hour)
- [ ] **AWS budget alerts configured** ($300/month)
- [ ] **CloudTrail enabled** (audit logging)
- [ ] **Team trained on incident response** (read DISASTER_RECOVERY_AND_INCIDENT_RESPONSE.md)

**Optional (Post-Launch):**
- [ ] Multi-region failover
- [ ] WAF enabled
- [ ] Advanced analytics

---

## **💰 COST SUMMARY**

### **Monthly Costs After Full Setup**

| Service | Cost | Required? |
|---------|------|-----------|
| ECS Fargate | $40-60 | ✅ Yes (existing) |
| RDS db.t3.micro | $12 | ✅ Yes (existing) |
| S3 storage + requests | $10-20 | ✅ Yes (existing) |
| ElastiCache Redis | $15 | ⚠️ **Required before launch** |
| CloudWatch metrics | $8 | ⚠️ **Required before launch** |
| StatusPage.io | $29 | ⚠️ **Recommended** |
| **TOTAL** | **~$114-144/month** | |

**ROI from Redis caching:** $30-50/month savings  
**Net cost increase:** $15-20/month

---

## **🚀 LAUNCH READINESS SCORE**

**Current Score: 7/10** ⚠️ **NOT READY FOR LAUNCH**

**To reach 10/10 (production-ready):**
1. ⚠️ Enable Redis caching (+1 point)
2. ⚠️ Deploy CloudWatch dashboard (+1 point)
3. ⚠️ Configure CloudWatch alarms with notifications (+1 point)

**Estimated time to launch-ready:** 4-6 hours

---

## **📞 SUPPORT CONTACTS**

- **AWS Support:** https://console.aws.amazon.com/support/
- **Clerk Support:** support@clerk.dev
- **Redis Cloud Support:** support@redis.com

---

**Next Steps:**
1. Complete the 3 critical tasks above
2. Run load testing
3. Test disaster recovery procedures
4. Deploy to production! 🚀

**Last Updated:** December 15, 2025  
**Document Owner:** Engineering Team  
**Review Schedule:** Before each major release

