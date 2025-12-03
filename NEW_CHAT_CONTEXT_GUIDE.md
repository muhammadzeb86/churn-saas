# 📋 **NEW CHAT CONTEXT GUIDE**

## **🎯 PURPOSE**
This file helps you start a new Cursor AI chat for Task 1.2+ without losing context from Task 1.1, while saving ~60-70% on costs.

---

## **📝 COPY-PASTE PROMPT FOR NEW CHAT**

```markdown
# Context: Continue Task 1.2 - Deploy Worker Service

## Background
I'm implementing a production-ready ML churn prediction SaaS (RetainWise Analytics).

**Task 1.1 Status:** ✅ COMPLETE
- SQS queues configured and deployed to AWS
- Backend code updated with SQS client and publisher
- GitHub Actions deployment successful
- All infrastructure validated

**Next Task:** Task 1.2 - Deploy Worker Service (6 hours estimated)

## Key Files to Reference
Please read these files first to understand the complete context:

1. **`ML_IMPLEMENTATION_MASTER_PLAN.md`** - Overall plan and phases
2. **`TASK_1.1_COMPLETE_SUMMARY.md`** - What was just completed
3. **`backend/services/sqs_client.py`** - SQS client implementation
4. **`backend/services/sqs_publisher.py`** - Message publishing logic
5. **`backend/schemas/sqs_messages.py`** - Message validation
6. **`infra/sqs-predictions.tf`** - SQS infrastructure
7. **`infra/iam-sqs-roles.tf`** - IAM roles and policies

## Current State
- **Environment:** Production (AWS ECS, no staging)
- **SQS Queue URL:** `https://sqs.us-east-1.amazonaws.com/908226940571/prod-retainwise-predictions-queue`
- **Backend Task Role:** `prod-retainwise-backend-task-role`
- **Worker Task Role:** `prod-retainwise-worker-task-role`
- **Region:** us-east-1
- **Repository:** muhammadzeb86/churn-saas

## Task 1.2 Requirements (from ML_IMPLEMENTATION_MASTER_PLAN.md)
1. Create ECS worker task definition
2. Implement SQS polling logic in `backend/workers/prediction_worker.py`
3. Connect to existing ML model (`backend/ml/predict.py`)
4. Test end-to-end prediction flow
5. Deploy worker service to ECS
6. Monitor processing times and errors

## Code Quality Standards
- **Production-only workflow** (no staging)
- **Highway-grade code** (no shortcuts or temporary solutions)
- **Security-first** (least privilege, input validation, error handling)
- **Cost-optimized** (efficient resource usage)
- **Fully documented** (comprehensive comments and docs)

## Important Notes
- We agreed to reject DeepSeek's "simple" solutions in favor of robust, production-grade implementations
- All security measures must remain intact (no downgrades for debugging)
- Follow the phased approach in ML_IMPLEMENTATION_MASTER_PLAN.md
- Pricing target: $79 Starter / $149 Professional with Phase 4 dashboard + SHAP

## Technical Stack Summary
- **Backend:** Python (FastAPI), SQLAlchemy (AsyncIO), Pydantic
- **ML:** XGBoost, scikit-learn, pandas, SHAP (to be added)
- **Infrastructure:** AWS ECS (Fargate), SQS, RDS (PostgreSQL), S3, ALB, CloudWatch
- **Auth:** Clerk JWT with signature verification
- **CI/CD:** GitHub Actions with OIDC
- **Deployment:** Terraform (infrastructure), Docker (containerization)

## Key Architectural Decisions
1. **ECS Worker (not Lambda)** - No timeout limits, no cold starts, better for ML
2. **Standard SQS Queue** - Unlimited throughput, 5-min visibility timeout
3. **3 Retries → DLQ** - Fast failure detection
4. **Dependency Injection** - SQS client lifecycle management
5. **Pydantic Validation** - Message structure validation
6. **Graceful Degradation** - System works even if SQS fails

## AWS Resources (Created in Task 1.1)
- **Main Queue:** `prod-retainwise-predictions-queue`
- **Dead Letter Queue:** `prod-retainwise-predictions-dlq`
- **Backend IAM Role:** Send messages only
- **Worker IAM Role:** Receive/delete messages only
- **CloudWatch Alarms:** DLQ monitoring, queue age alerts

## Request
Please proceed with Task 1.2: Deploy Worker Service according to the master plan. 

Start by:
1. Reading the master plan and Task 1.1 summary
2. Reviewing existing SQS implementation
3. Creating production-grade worker service code
4. Providing deployment instructions

Let's maintain the same quality and attention to detail as Task 1.1.
```

---

## **📚 CRITICAL FILES TO KEEP**

These files contain all the context you need:

### **Planning & Architecture:**
- ✅ `ML_IMPLEMENTATION_MASTER_PLAN.md` - Complete roadmap
- ✅ `TASK_1.1_COMPLETE_SUMMARY.md` - Task 1.1 recap
- ✅ `TASK_1.1_SQS_IMPLEMENTATION.md` - Technical details

### **Infrastructure:**
- ✅ `infra/sqs-predictions.tf` - SQS queues
- ✅ `infra/iam-sqs-roles.tf` - IAM roles
- ✅ `infra/ecs-worker.tf` - Worker service skeleton
- ✅ `infra/variables.tf` - Configuration

### **Backend Code:**
- ✅ `backend/services/sqs_client.py` - Client management
- ✅ `backend/services/sqs_publisher.py` - Publishing logic
- ✅ `backend/schemas/sqs_messages.py` - Validation
- ✅ `backend/core/config.py` - SQS settings
- ✅ `backend/workers/prediction_worker.py` - Worker (to be enhanced)
- ✅ `backend/ml/predict.py` - ML model

---

## **💡 TIPS FOR NEW CHAT**

### **1. Start with Context Load**
Paste the prompt above, then ask:
```
Please read and confirm you understand:
1. ML_IMPLEMENTATION_MASTER_PLAN.md
2. TASK_1.1_COMPLETE_SUMMARY.md

Then let me know when you're ready to start Task 1.2.
```

### **2. Reference Files Explicitly**
When you need specific details:
```
Please review backend/services/sqs_publisher.py and explain 
how the graceful degradation works.
```

### **3. Use Incremental Requests**
Instead of:
- ❌ "Implement entire Task 1.2"

Break it down:
- ✅ "Step 1: Create worker polling logic"
- ✅ "Step 2: Integrate with ML model"
- ✅ "Step 3: Deploy to ECS"

This keeps costs down and gives you more control.

---

## **💰 COST OPTIMIZATION STRATEGIES**

### **1. Use Smaller Model for Simple Tasks**
- Switch to Claude Sonnet 3.5 or GPT-4 for planning
- Use Claude Opus only for critical code generation

### **2. Batch Related Questions**
Instead of:
- ❌ 3 separate chats about worker, testing, deployment

Do:
- ✅ 1 chat covering worker + testing + deployment

### **3. Use Cursor's Native Features**
- Use Cursor's file search instead of asking AI
- Use Cursor's diff view instead of asking for comparisons
- Use Cursor's terminal instead of asking for commands

### **4. Reference Documentation Directly**
For standard patterns, use docs instead of AI:
- AWS ECS documentation
- FastAPI documentation
- SQLAlchemy patterns

Save AI for **custom business logic and architecture**.

---

## **🎯 WHEN TO START NEW CHAT**

Start a new chat when:
- ✅ Completing a major phase (Task 1.1 → 1.2 → 1.3)
- ✅ Context exceeds 50K tokens
- ✅ Responses become slow or expensive
- ✅ Switching from planning to implementation

**DON'T start new chat when:**
- ❌ In the middle of debugging
- ❌ Making related quick fixes
- ❌ Iterating on a specific file

---

## **📊 EXPECTED COSTS**

### **Task 1.2 (Worker Service):**
- With this chat continuation: ~$6-8
- With new chat + context files: ~$2-3
- **Savings: 60-70%**

### **Complete Phase 1 (10 tasks):**
- Old approach: ~$60-80
- New approach: ~$20-30
- **Savings: ~$40-50**

---

## **✅ CHECKLIST FOR NEW CHAT**

Before starting:
- [ ] Read `ML_IMPLEMENTATION_MASTER_PLAN.md`
- [ ] Read `TASK_1.1_COMPLETE_SUMMARY.md`
- [ ] Copy prompt from this file
- [ ] Paste into new Cursor AI chat
- [ ] Wait for AI to confirm it read the files
- [ ] Begin Task 1.2

---

## **🚀 READY TO START?**

1. Open new Cursor AI chat
2. Copy the prompt from above
3. Paste and send
4. Proceed with Task 1.2!

**You'll save 60-70% on costs while maintaining full context.** 💰✅

