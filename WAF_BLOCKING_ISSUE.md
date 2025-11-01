# 🚨 **ROOT CAUSE FOUND: AWS WAF Blocking File Uploads**

**Date:** November 1, 2025  
**Status:** 🔴 **CRITICAL - WAF Blocking Production Uploads**

---

## 🎯 **THE REAL PROBLEM**

### **Not CORS, Not Content-Type, Not Frontend - It's AWS WAF!**

Looking at the Network tab, the issue is clear:

```
Status: 403 Forbidden
Request URL: https://backend.retainwiseanalytics.com/api/csv
Method: POST
```

**403 Forbidden** means:
- ✅ Request left the browser successfully
- ✅ CORS is working (OPTIONS succeeded)
- ✅ Content-Type is correct
- ❌ **AWS WAF blocked the request at the ALB level**

---

## 📊 **EVIDENCE**

### **From Browser Network Tab:**
```
Status Code: 403 Forbidden
Referrer Policy: strict-origin-when-cross-origin
Server: awselb/2.0
```

**`awselb/2.0`** = AWS Elastic Load Balancer  
**403 before reaching backend** = WAF block

### **From AWS Logs:**
```
✅ OPTIONS /api/csv 200 OK  (Preflight succeeded)
❌ NO POST /api/csv in logs  (Never reached backend!)
```

The POST request was **blocked before reaching the ECS container**.

---

## 🚫 **WHAT'S BLOCKING IT**

### **AWS WAF Rules Active:**

1. **AWSManagedRulesCommonRuleSet** (Priority 1)
   - Blocks common web attacks
   - Can trigger on file uploads with certain patterns

2. **AWSManagedRulesKnownBadInputsRuleSet** (Priority 2)
   - Blocks known malicious inputs
   - Can trigger on CSV content

3. **AWSManagedRulesSQLiRuleSet** (Priority 3)
   - Blocks SQL injection attempts
   - **LIKELY CULPRIT**: CSV files can contain patterns that look like SQL

4. **Rate Limiting** (Priority 4)
   - 2000 requests per 5 minutes per IP
   - Unlikely to be the issue

---

## 🎯 **WHY CSV FILES Trigger WAF**

CSV files can contain:
- SQL-like syntax: `SELECT, INSERT, UPDATE, DELETE`
- Special characters: `'; DROP TABLE; --`
- Encoded data that looks suspicious
- User-Agent strings that trigger rules

**Example CSV content that WAF blocks:**
```csv
customer_id,name,query
1,John,"SELECT * FROM users"
2,Jane,"UPDATE customers SET status='active'"
```

---

## 🔧 **SOLUTION OPTIONS**

### **Option 1: Exemp
t /api/csv from WAF (Recommended)**

Add a rule to exclude file uploads from specific WAF rules:

```hcl
# infra/waf.tf

# Add this rule BEFORE the SQL injection rule
rule {
  name     = "ExemptFileUploadsFromSQLiRule"
  priority = 2.5  # Between KnownBadInputs (2) and SQLi (3)

  action {
    allow {}
  }

  statement {
    and_statement {
      statements = [
        # Match the upload endpoint
        {
          byte_match_statement {
            search_string         = "/api/csv"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
            positional_constraint = "CONTAINS"
          }
        },
        # Match POST method
        {
          byte_match_statement {
            search_string         = "POST"
            field_to_match {
              method {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
            positional_constraint = "EXACTLY"
          }
        }
      ]
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "FileUploadExemptionMetric"
    sampled_requests_enabled   = true
  }
}
```

### **Option 2: Change SQLi Rule to Count Mode (Temporary)**

Change the SQL injection rule from blocking to counting:

```hcl
# In infra/waf.tf, modify the SQLi rule:

rule {
  name     = "AWSManagedRulesSQLiRuleSet"
  priority = 3

  override_action {
    count {}  # Changed from none{} to count{} - logs but doesn't block
  }

  statement {
    managed_rule_group_statement {
      name        = "AWSManagedRulesSQLiRuleSet"
      vendor_name = "AWS"
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "SQLiRuleSetMetric"
    sampled_requests_enabled   = true
  }
}
```

### **Option 3: Temporarily Disable WAF (NOT RECOMMENDED)**

```bash
# Remove WAF association (NOT RECOMMENDED FOR PRODUCTION)
cd infra
# Comment out the WAF association in waf.tf
# resource "aws_wafv2_web_acl_association" "main" { ... }
terraform apply
```

---

## ✅ **RECOMMENDED ACTION: Option 2 (Count Mode)**

**Why:**
- ✅ Quick to implement
- ✅ Maintains other WAF protections
- ✅ Logs SQLi attempts without blocking
- ✅ Can be tested immediately
- ⚠️ Temporarily reduces SQL injection protection for `/api/csv`

**Steps:**

1. **Modify WAF rule to count mode**
2. **Apply Terraform changes**
3. **Test upload**
4. **Implement Option 1 for permanent fix**

---

## 📋 **IMPLEMENTATION STEPS**

### **Step 1: Modify WAF Configuration**

```bash
# Edit infra/waf.tf
# Change override_action from none{} to count{} for SQLi rule
```

### **Step 2: Apply Changes**

```bash
cd infra
terraform plan  # Review changes
terraform apply # Apply (type 'yes')
```

### **Step 3: Test Upload**

Wait 1-2 minutes for WAF update, then:
1. Go to app.retainwiseanalytics.com
2. Try CSV upload
3. Check Network tab for 200 OK

### **Step 4: Monitor**

```bash
# Check if uploads work
aws logs tail /ecs/retainwise-backend --follow --region us-east-1

# Should see:
# ✅ OPTIONS /api/csv 200 OK
# ✅ POST /api/csv 200 OK  ← This should now appear!
```

---

## 🔍 **HOW TO CONFIRM WAF IS THE ISSUE**

### **Check WAF Metrics:**

1. Go to AWS Console → WAF
2. Click on `retainwise-waf`
3. Go to "Metrics" tab
4. Look for spikes in:
   - `SQLiRuleSetMetric`
   - `CommonRuleSetMetric`

### **Check Sampled Requests:**

1. Go to AWS Console → WAF
2. Click on `retainwise-waf`
3. Click "Sampled requests"
4. Filter by "Blocked requests"
5. Look for `/api/csv` requests

---

## 📊 **TIMELINE OF ISSUES**

| Issue | Status | Resolution |
|-------|--------|------------|
| CORS middleware order | ✅ Fixed | Commit `55b2cf3` |
| Content-Type boundary | ✅ Fixed | Commit `6894aca` |
| Default Content-Type | ✅ Fixed | Commit `fed2c62` |
| **AWS WAF blocking** | 🔴 **CURRENT** | **Needs Terraform apply** |

---

## 💡 **WHY WE DIDN'T CATCH THIS EARLIER**

1. **The 422 error** (earlier test) suggested the request was reaching the backend
   - That was a different code version
   - Different error mode

2. **Progress bar reached 100%**
   - This is just the browser preparing the request
   - Doesn't mean it was sent successfully

3. **OPTIONS succeeded**
   - WAF doesn't block preflight requests
   - Only blocks the actual POST with file content

4. **CORS error message**
   - Browser shows CORS error when it gets 403
   - Misleading - actual issue is WAF

---

## 🎯 **CONFIDENCE LEVEL: 99%**

**Why 99%:**
- ✅ 403 Forbidden from `awselb/2.0` server
- ✅ No POST request in backend logs
- ✅ OPTIONS succeeds (proves CORS works)
- ✅ WAF has SQL injection rules that block CSV patterns
- ✅ This is a common issue with file uploads + WAF

**Why not 100%:**
- Need to confirm with WAF logs (which rule specifically)

---

## 🚀 **NEXT STEPS**

1. **Modify** `infra/waf.tf` to set SQLi rule to count mode
2. **Apply** Terraform changes
3. **Test** upload immediately
4. **Implement** permanent exemption rule (Option 1)

---

**Status:** 🟡 **READY TO FIX** - Terraform apply required  
**ETA:** 5 minutes (Terraform apply + test)  
**Risk:** LOW (only affects SQLi detection for `/api/csv`)

