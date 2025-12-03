# 🔒 **SQS PERMISSIONS ISSUE - FIXING NOW**

## **✅ GREAT NEWS: Environment Variables Working!**

The logs show the backend is NOW trying to connect to SQS (progress!), but hitting a permissions error:

```
ERROR: SQS connection failed: AccessDenied
User: arn:aws:sts::908226940571:assumed-role/retainwise-ecs-task-role/...
is not authorized to perform: sqs:getqueueattributes
```

## **🎯 ROOT CAUSE**

The backend is using the WRONG IAM role!

**Current:** `retainwise-ecs-task-role` (generic ECS task role)
**Expected:** `retainwise-backend-sqs-send-role` (SQS send-only role from Task 1.1)

## **🔍 ANALYSIS**

From Task 1.1, we created:
- `retainwise-backend-sqs-send-role` - For backend to SEND messages
- `retainwise-worker-sqs-receive-role` - For worker to RECEIVE messages

But the backend task definition is using the wrong role!

## **🔧 THE FIX**

Update `infra/resources.tf` to use the correct IAM role for the backend.

