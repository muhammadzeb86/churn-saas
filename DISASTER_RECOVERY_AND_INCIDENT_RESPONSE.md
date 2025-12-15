# 🚨 **DISASTER RECOVERY & INCIDENT RESPONSE PLAN**

**Document Owner:** RetainWise Engineering
**Last Updated:** December 15, 2025  
**Version:** 1.0  
**Review Schedule:** Monthly

---

## **📋 TABLE OF CONTENTS**

1. [Emergency Contacts](#emergency-contacts)
2. [Incident Response Procedure](#incident-response-procedure)
3. [Disaster Recovery Procedures](#disaster-recovery-procedures)
4. [Database Backup & Restore](#database-backup--restore)
5. [S3 Data Recovery](#s3-data-recovery)
6. [Rollback Procedures](#rollback-procedures)
7. [Common Incidents & Solutions](#common-incidents--solutions)
8. [Post-Incident Review](#post-incident-review)

---

## **🆘 EMERGENCY CONTACTS**

### **On-Call Schedule**

| Role | Primary | Secondary |
|------|---------|-----------|
| **Engineering Lead** | [Name] | [Name] |
| **DevOps** | [Name] | [Name] |
| **Database Admin** | [Name] | [Name] |

### **Escalation Path**

```
Level 1: On-Call Engineer (responds in 15 minutes)
   ↓
Level 2: Engineering Lead (if unresolved in 30 minutes)
   ↓
Level 3: CTO (if critical impact >1 hour)
```

### **Communication Channels**

- **Incident Slack**: `#incidents`
- **Status Page**: https://status.retainwise.ai
- **Pager**: PagerDuty (auto-escalates from CloudWatch alarms)

---

## **🔥 INCIDENT RESPONSE PROCEDURE**

### **Step 1: DETECTION (Minutes 0-5)**

**How You'll Know:**
- CloudWatch alarm triggers
- User reports issue
- Error rate spike in dashboard
- Customer support ticket

**First Actions:**
1. **Acknowledge the incident** in Slack `#incidents`
2. **Check the dashboard**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=RetainWise-Production
3. **Assess severity** (see table below)

### **Severity Levels**

| Severity | Definition | Response Time | Example |
|----------|------------|---------------|---------|
| **P0 (Critical)** | Service down, data loss | <15 min | RDS database unreachable, S3 bucket deleted |
| **P1 (High)** | Major functionality broken | <30 min | Predictions failing, uploads failing |
| **P2 (Medium)** | Partial functionality issue | <2 hours | Slow performance, some users affected |
| **P3 (Low)** | Minor issue, workaround exists | <24 hours | UI bug, log noise |

### **Step 2: TRIAGE (Minutes 5-15)**

**Checklist:**
- [ ] **Post in `#incidents`**: `🚨 INCIDENT: [Brief description] - Severity: PX`
- [ ] **Create incident doc**: [Use template below](#incident-template)
- [ ] **Check CloudWatch Logs**:
  ```bash
  aws logs tail /ecs/retainwise-worker --follow --since 30m --region us-east-1
  aws logs tail /ecs/retainwise-service --follow --since 30m --region us-east-1
  ```
- [ ] **Run CloudWatch Insights queries**:
  ```sql
  # Recent failures
  fields @timestamp, prediction_id, error_type, error_message
  | filter event = 'prediction_failed'
  | sort @timestamp desc
  | limit 20
  ```

### **Step 3: MITIGATION (Minutes 15-60)**

**Goal:** Stop the bleeding, restore service (even if imperfect)

**Common Quick Fixes:**
1. **Service degraded?** → Scale up ECS tasks
   ```bash
   aws ecs update-service \
     --cluster retainwise-cluster \
     --service retainwise-worker \
     --desired-count 3 \
     --region us-east-1
   ```

2. **Bad deployment?** → Rollback immediately (see [Rollback Procedures](#rollback-procedures))

3. **Database slow?** → Check active connections
   ```bash
   # SSH to RDS bastion, then psql
   SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
   
   # Kill long-running queries
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';
   ```

4. **S3 issues?** → Check IAM permissions & bucket policy

### **Step 4: RESOLUTION (Minutes 60+)**

**Goal:** Permanent fix, root cause elimination

**Actions:**
- [ ] Implement proper fix
- [ ] Test fix in staging
- [ ] Deploy fix with monitoring
- [ ] Verify resolution in production
- [ ] Update runbook with new learnings

### **Step 5: POST-MORTEM (Within 48 hours)**

See [Post-Incident Review](#post-incident-review)

---

## **🔄 DISASTER RECOVERY PROCEDURES**

### **DR Scenario 1: Complete RDS Database Loss**

**Recovery Time Objective (RTO):** 4 hours  
**Recovery Point Objective (RPO):** 1 hour (automated backups)

**Procedure:**

1. **Verify database is truly down**
   ```bash
   # Try to connect
   psql -h retainwise-db.xyz.us-east-1.rds.amazonaws.com -U admin -d churn_production
   
   # Check RDS status
   aws rds describe-db-instances \
     --db-instance-identifier retainwise-db \
     --region us-east-1 \
     --query 'DBInstances[0].DBInstanceStatus'
   ```

2. **Check latest automated backup**
   ```bash
   aws rds describe-db-snapshots \
     --db-instance-identifier retainwise-db \
     --region us-east-1 \
     --query 'DBSnapshots[0].[DBSnapshotIdentifier,SnapshotCreateTime]'
   ```

3. **Restore from latest snapshot**
   ```bash
   # Restore to new instance (faster than in-place restore)
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier retainwise-db-restored \
     --db-snapshot-identifier rds:retainwise-db-YYYY-MM-DD-HH-MM \
     --db-instance-class db.t3.micro \
     --region us-east-1
   
   # Wait for available status (~15-30 minutes)
   aws rds wait db-instance-available \
     --db-instance-identifier retainwise-db-restored \
     --region us-east-1
   ```

4. **Update connection strings**
   ```bash
   # Update ECS task definitions with new RDS endpoint
   # Option 1: Use AWS Systems Manager Parameter Store
   aws ssm put-parameter \
     --name /retainwise/prod/db_host \
     --value "retainwise-db-restored.xyz.us-east-1.rds.amazonaws.com" \
     --type SecureString \
     --overwrite \
     --region us-east-1
   
   # Option 2: Update environment variables in ECS task definition
   # (Requires redeployment)
   ```

5. **Force ECS service redeployment**
   ```bash
   aws ecs update-service \
     --cluster retainwise-cluster \
     --service retainwise-service \
     --force-new-deployment \
     --region us-east-1
   
   aws ecs update-service \
     --cluster retainwise-cluster \
     --service retainwise-worker \
     --force-new-deployment \
     --region us-east-1
   ```

6. **Verify recovery**
   ```bash
   # Check database connectivity
   psql -h retainwise-db-restored.xyz.us-east-1.rds.amazonaws.com -U admin -d churn_production -c "SELECT COUNT(*) FROM predictions;"
   
   # Check service health
   curl https://api.retainwise.ai/health
   ```

7. **Data loss assessment**
   ```sql
   -- Check latest prediction timestamp
   SELECT MAX(created_at) FROM predictions;
   
   -- Compare with backup time to determine data loss window
   ```

**Expected Data Loss:** Maximum 1 hour (between automated backups)

---

### **DR Scenario 2: S3 Bucket Accidentally Deleted**

**RTO:** 2 hours  
**RPO:** 0 (versioning enabled)

**Procedure:**

1. **Enable S3 versioning** (if not already enabled)
   ```bash
   aws s3api put-bucket-versioning \
     --bucket retainwise-predictions \
     --versioning-configuration Status=Enabled \
     --region us-east-1
   ```

2. **List deleted objects**
   ```bash
   aws s3api list-object-versions \
     --bucket retainwise-predictions \
     --prefix "predictions/" \
     --query "DeleteMarkers[?IsLatest]" \
     --region us-east-1
   ```

3. **Restore deleted objects**
   ```bash
   # Restore all versioned objects
   aws s3api list-object-versions \
     --bucket retainwise-predictions \
     --query "Versions[?IsLatest].[Key,VersionId]" \
     --output text | \
   while read key versionId; do
     aws s3api copy-object \
       --bucket retainwise-predictions \
       --copy-source "retainwise-predictions/${key}?versionId=${versionId}" \
       --key "${key}" \
       --region us-east-1
   done
   ```

4. **Verify restoration**
   ```bash
   # Count objects
   aws s3 ls s3://retainwise-predictions/predictions/ --recursive | wc -l
   
   # Verify latest prediction files exist
   aws s3 ls s3://retainwise-predictions/predictions/ --recursive --human-readable | tail -n 20
   ```

**Prevention:**
- **MFA Delete**: Require multi-factor authentication for bucket deletion
  ```bash
  aws s3api put-bucket-versioning \
    --bucket retainwise-predictions \
    --versioning-configuration Status=Enabled,MFADelete=Enabled \
    --mfa "arn:aws:iam::123456789:mfa/root-account-mfa-device XXXXXX" \
    --region us-east-1
  ```

---

### **DR Scenario 3: AWS Region Outage (us-east-1)**

**RTO:** 8 hours  
**RPO:** 4 hours (cross-region replication)

**Procedure:**

**Current State (MVP):**
- ❌ No cross-region replication configured
- ❌ Single-region deployment

**Future State (When Revenue > $50K/month):**
- ✅ RDS cross-region read replica (us-west-2)
- ✅ S3 cross-region replication
- ✅ Multi-region ECS deployment

**Workaround for MVP:**
1. **Wait for AWS region recovery** (typically <4 hours)
2. **Communicate downtime** via status page
3. **No data loss** (RDS automated backups persist across region outages)

---

## **💾 DATABASE BACKUP & RESTORE**

### **Automated Backups (Enabled)**

**Configuration:**
- **Retention:** 7 days
- **Frequency:** Daily at 03:00 UTC
- **Backup window:** 03:00 - 04:00 UTC
- **Maintenance window:** Sun 04:00 - 05:00 UTC

**Verify Automated Backups:**
```bash
# List all automated backups
aws rds describe-db-snapshots \
  --db-instance-identifier retainwise-db \
  --snapshot-type automated \
  --region us-east-1 \
  --query 'DBSnapshots[].[DBSnapshotIdentifier,SnapshotCreateTime,Status]' \
  --output table
```

### **Manual Backup (Before Major Changes)**

**When to Create:**
- Before database migrations
- Before major schema changes
- Before large data imports
- Monthly (last Sunday of month)

**Create Manual Snapshot:**
```bash
# Create snapshot
aws rds create-db-snapshot \
  --db-instance-identifier retainwise-db \
  --db-snapshot-identifier retainwise-db-manual-$(date +%Y-%m-%d) \
  --region us-east-1

# Wait for completion (~5-10 minutes)
aws rds wait db-snapshot-completed \
  --db-snapshot-identifier retainwise-db-manual-$(date +%Y-%m-%d) \
  --region us-east-1

echo "✅ Snapshot created successfully"
```

### **Point-in-Time Recovery (PITR)**

RDS supports PITR for last 7 days (to any second).

**Restore to Specific Time:**
```bash
# Restore to 2 hours ago
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier retainwise-db \
  --target-db-instance-identifier retainwise-db-restored \
  --restore-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --region us-east-1
```

### **Backup Verification (Weekly)**

**Automated Test Script** (`scripts/verify_backups.sh`):
```bash
#!/bin/bash
# Verify database backups exist and are restorable

set -e

echo "🔍 Verifying RDS backups..."

# Check latest automated backup
LATEST_BACKUP=$(aws rds describe-db-snapshots \
  --db-instance-identifier retainwise-db \
  --snapshot-type automated \
  --region us-east-1 \
  --query 'DBSnapshots[0].[DBSnapshotIdentifier,SnapshotCreateTime]' \
  --output text)

echo "Latest backup: $LATEST_BACKUP"

# Check backup age
BACKUP_TIME=$(echo $LATEST_BACKUP | awk '{print $2}')
BACKUP_AGE_HOURS=$(( ($(date +%s) - $(date -d "$BACKUP_TIME" +%s)) / 3600 ))

if [ $BACKUP_AGE_HOURS -gt 26 ]; then
  echo "❌ WARNING: Backup is $BACKUP_AGE_HOURS hours old (expected <26 hours)"
  exit 1
else
  echo "✅ Backup is fresh ($BACKUP_AGE_HOURS hours old)"
fi

# Verify backup size
BACKUP_SIZE=$(aws rds describe-db-snapshots \
  --db-instance-identifier retainwise-db \
  --snapshot-type automated \
  --region us-east-1 \
  --query 'DBSnapshots[0].AllocatedStorage' \
  --output text)

echo "✅ Backup size: ${BACKUP_SIZE}GB"

echo "✅ All backup verifications passed!"
```

**Schedule:** Run weekly via GitHub Actions

---

## **📦 S3 DATA RECOVERY**

### **S3 Versioning (Enabled)**

**Configuration:**
```bash
# Verify versioning is enabled
aws s3api get-bucket-versioning \
  --bucket retainwise-predictions \
  --region us-east-1

# Expected output: {"Status": "Enabled"}
```

### **Recover Accidentally Deleted File**

**Scenario:** User accidentally deleted a prediction CSV

```bash
# 1. Find the deleted file's version ID
aws s3api list-object-versions \
  --bucket retainwise-predictions \
  --prefix "predictions/user123/prediction456.csv" \
  --region us-east-1 \
  --query "Versions[?IsLatest].VersionId" \
  --output text

# 2. Copy the version to restore it
aws s3api copy-object \
  --bucket retainwise-predictions \
  --copy-source "retainwise-predictions/predictions/user123/prediction456.csv?versionId=VERSION_ID_HERE" \
  --key "predictions/user123/prediction456.csv" \
  --region us-east-1

echo "✅ File restored successfully"
```

### **S3 Lifecycle Policy (Cost Optimization)**

**Transition old predictions to cheaper storage:**
```json
{
  "Rules": [
    {
      "Id": "archive-old-predictions",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "predictions/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 365,
          "StorageClass": "GLACIER"
        }
      ],
      "NoncurrentVersionTransitions": [
        {
          "NoncurrentDays": 30,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

**Apply lifecycle policy:**
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket retainwise-predictions \
  --lifecycle-configuration file://s3-lifecycle.json \
  --region us-east-1
```

---

## **🔙 ROLLBACK PROCEDURES**

### **Rollback Scenario 1: Bad Backend Deployment**

**Detection:**
- High error rate after deployment
- CloudWatch alarm triggered
- User reports bugs

**Rollback Steps (< 5 minutes):**

```bash
# 1. Find previous working task definition
aws ecs list-task-definitions \
  --family-prefix retainwise-service \
  --status ACTIVE \
  --region us-east-1 \
  --query 'taskDefinitionArns[-2]' \
  --output text

# Example output: arn:aws:ecs:us-east-1:123456789:task-definition/retainwise-service:42

# 2. Update service to use previous task definition
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --task-definition retainwise-service:42 \
  --force-new-deployment \
  --region us-east-1

# 3. Do the same for worker
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --task-definition retainwise-worker:42 \
  --force-new-deployment \
  --region us-east-1

# 4. Wait for deployment
aws ecs wait services-stable \
  --cluster retainwise-cluster \
  --services retainwise-service retainwise-worker \
  --region us-east-1

echo "✅ Rollback complete"
```

### **Rollback Scenario 2: Bad Database Migration**

**Detection:**
- Application errors after `alembic upgrade head`
- Schema incompatibility

**Rollback Steps:**

```bash
# 1. SSH to application server or use RDS bastion

# 2. Check current migration version
psql -h retainwise-db.xyz.us-east-1.rds.amazonaws.com -U admin -d churn_production -c \
  "SELECT version_num FROM alembic_version;"

# 3. Rollback one migration
cd /path/to/backend
alembic downgrade -1

# 4. Verify rollback
alembic current

# 5. Restart services (to reload schema)
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-service \
  --force-new-deployment \
  --region us-east-1
```

**CRITICAL:** Always test migrations in staging first!

---

## **🔍 COMMON INCIDENTS & SOLUTIONS**

### **Incident: "Predictions Stuck in PENDING"**

**Symptoms:**
- Predictions not processing
- SQS queue depth increasing
- Worker logs show no activity

**Diagnosis:**
```bash
# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789/retainwise-predictions \
  --attribute-names ApproximateNumberOfMessages \
  --region us-east-1

# Check worker task count
aws ecs describe-services \
  --cluster retainwise-cluster \
  --services retainwise-worker \
  --region us-east-1 \
  --query 'services[0].runningCount'
```

**Solution:**
```bash
# Scale up worker tasks
aws ecs update-service \
  --cluster retainwise-cluster \
  --service retainwise-worker \
  --desired-count 3 \
  --region us-east-1
```

---

### **Incident: "High Latency (P95 > 2000ms)"**

**Symptoms:**
- Slow predictions
- User complaints
- CloudWatch alarm

**Diagnosis:**
```sql
-- Check slow queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > INTERVAL '1 second'
ORDER BY duration DESC;
```

**Solution:**
1. Check for missing indexes
2. Check for lock contention
3. Scale up RDS instance temporarily

---

### **Incident: "S3 Upload Failures"**

**Symptoms:**
- `S3UploadError` in logs
- Error rate spike
- Prediction CSV not generated

**Diagnosis:**
```bash
# Check IAM permissions
aws iam get-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-name S3AccessPolicy \
  --region us-east-1

# Check bucket exists
aws s3 ls s3://retainwise-predictions/
```

**Solution:**
- Verify IAM policy grants `s3:PutObject`
- Check S3 bucket policy
- Verify ECS task role is attached

---

## **📝 POST-INCIDENT REVIEW**

### **Incident Template**

```markdown
# Incident Post-Mortem: [TITLE]

**Date:** YYYY-MM-DD  
**Severity:** P0/P1/P2/P3  
**Duration:** HH:MM  
**Impact:** X customers affected

## Timeline

- **HH:MM** - Incident detected (CloudWatch alarm)
- **HH:MM** - Engineering team notified
- **HH:MM** - Root cause identified
- **HH:MM** - Mitigation deployed
- **HH:MM** - Service restored

## Root Cause

[Detailed technical explanation]

## Resolution

[What was done to fix it]

## Impact

- **Users affected:** X
- **Predictions lost:** Y
- **Revenue impact:** $Z
- **Downtime:** HH:MM

## Prevention

### Immediate (< 1 week)
- [ ] Action item 1
- [ ] Action item 2

### Short-term (< 1 month)
- [ ] Action item 3
- [ ] Action item 4

### Long-term (< 3 months)
- [ ] Action item 5

## Lessons Learned

1. What went well?
2. What went wrong?
3. What could we have done better?
```

### **Post-Mortem Process**

1. **Schedule within 48 hours** of incident
2. **Invite all stakeholders** (engineering, product, support)
3. **Focus on systems, not blame** ("blameless post-mortem")
4. **Document action items** in Jira/Linear
5. **Track action items to completion**
6. **Update runbooks** with new learnings

---

## **✅ DISASTER RECOVERY CHECKLIST**

### **Monthly Verification**
- [ ] Verify automated RDS backups exist (< 26 hours old)
- [ ] Test PITR restore to staging
- [ ] Verify S3 versioning enabled
- [ ] Review CloudWatch alarms (no false positives)
- [ ] Update on-call schedule

### **Quarterly Drill**
- [ ] Full database restore drill (staging)
- [ ] S3 bucket recovery drill
- [ ] ECS rollback drill
- [ ] Documentation review & update

---

## **📞 SUPPORT RESOURCES**

- **AWS Support:** https://console.aws.amazon.com/support/
- **RDS Documentation:** https://docs.aws.amazon.com/rds/
- **ECS Documentation:** https://docs.aws.amazon.com/ecs/
- **S3 Documentation:** https://docs.aws.amazon.com/s3/

---

**END OF DOCUMENT**

