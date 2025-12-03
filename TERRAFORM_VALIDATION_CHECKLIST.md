# 🔍 **COMPLETE TERRAFORM VALIDATION CHECKLIST**

## **Pre-Deployment Validation - Task 1.2**

This is our 5th attempt. Let's systematically check EVERYTHING.

---

## **✅ VALIDATION CHECKLIST**

### **1. Resource References**
- [ ] All `aws_iam_role` references are valid
- [ ] All `aws_sqs_queue` references are valid
- [ ] All `aws_s3_bucket` references are valid
- [ ] All `data` sources exist
- [ ] No circular dependencies

### **2. Variable Definitions**
- [ ] All variables used are defined in `variables.tf`
- [ ] No undefined variables
- [ ] Default values provided where needed

### **3. File Dependencies**
- [ ] `iam-sqs-roles.tf` can be applied independently
- [ ] `iam-cicd-restrictions.tf` doesn't break on first apply
- [ ] Cross-file references use ARNs or explicit depends_on

### **4. Resource Names**
- [ ] No duplicate resource names
- [ ] Consistent naming conventions
- [ ] Names match AWS constraints

### **5. Syntax**
- [ ] Valid HCL syntax
- [ ] Proper JSON encoding in policies
- [ ] Correct interpolation syntax

---

## **🔍 CHECKING NOW...**

