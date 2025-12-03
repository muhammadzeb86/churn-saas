# 🔧 **MANUAL WAF FIX - AWS Console Instructions**

## **Why Manual Fix is Needed**

- GitHub Actions detected infra changes but didn't run Terraform
- Terraform is not installed locally
- Fastest solution: Update WAF directly in AWS Console (5 minutes)

---

## **📋 STEP-BY-STEP INSTRUCTIONS**

### **Step 1: Open AWS WAF Console**

1. Go to: https://console.aws.amazon.com/wafv2/
2. **Region:** Ensure you're in **US East (N. Virginia) us-east-1**
3. Click on **"Web ACLs"** in the left sidebar

### **Step 2: Find Your WAF**

1. Click on **"retainwise-waf"**
2. You should see it associated with your load balancer

### **Step 3: Edit SQL Injection Rule**

1. Click on the **"Rules"** tab
2. Find the rule named: **"AWSManagedRulesSQLiRuleSet"**
3. Click the **checkbox** next to it
4. Click **"Edit"** button at the top

### **Step 4: Change to Count Mode**

1. In the edit screen, find **"Override rule group action"** section
2. Change from:
   - ❌ **"Use rule group configuration"** or **"None"**
   
   To:
   - ✅ **"Count"**

3. Scroll down and click **"Save rule"**

### **Step 5: Save WAF Configuration**

1. After the rule is saved, you might need to click **"Save"** again at the WAF level
2. Wait 30 seconds for changes to propagate

---

## **🎯 VERIFICATION**

After saving:
1. Go back to app.retainwiseanalytics.com/upload
2. Try uploading your CSV file
3. **Expected Result:**
   - ✅ No 403 Forbidden error
   - ✅ Upload completes successfully
   - ✅ Backend logs show `POST /api/csv 200 OK`

---

## **📊 WHAT THIS CHANGES**

**Before:**
- SQL injection rule: **BLOCK** mode
- CSV files with SQL patterns → 403 Forbidden

**After:**
- SQL injection rule: **COUNT** mode  
- CSV files with SQL patterns → Allowed
- Still logs potential SQLi for monitoring

---

## **⏱️ TIME REQUIRED**

- Console navigation: 1 minute
- Edit rule: 2 minutes
- Save & propagate: 1 minute
- **Total: ~5 minutes**

---

## **🔄 ALTERNATIVE: Wait for Next Deployment**

If you don't want to use the console, you can:
1. Make a small code change (e.g., add a comment)
2. Push to GitHub
3. Wait for CI/CD
4. Manually run Terraform in the workflow

But console fix is **much faster** (5 min vs 20 min).

---

## **❓ NEED HELP?**

If you have trouble finding the WAF or editing the rule:
1. Take a screenshot of the AWS WAF console
2. I'll provide more specific guidance

---

**Status:** 🟡 **READY FOR MANUAL FIX**  
**Time:** 5 minutes  
**Difficulty:** Easy (just toggle a setting)

