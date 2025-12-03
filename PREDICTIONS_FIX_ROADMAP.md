# 🔧 **PREDICTIONS ERROR - FIX ROADMAP & IMPLEMENTATION PLAN**

## **📋 ISSUE SUMMARY**

**Error:**
```
❌ GET /api/predictions?user_id=user_XXX → 500 Internal Server Error
❌ Error: invalid UUID 'predictions': length must be between 32..36 characters, got 11
❌ SQL: WHERE predictions.id = $1::UUID
❌ [parameters: ('predictions',)]
```

**Frontend Call:**
```typescript
// frontend/src/services/api.ts
getPredictions: (userId: string) => api.get('/api/predictions', {
  params: { user_id: userId }
})
```

**Expected:** `GET /api/predictions?user_id=...` returns list of predictions  
**Actual:** Route is being interpreted as `GET /api/{prediction_id}` where `prediction_id='predictions'`

---

## **🎯 ROOT CAUSE ANALYSIS**

### **Problem: Incorrect Router Mounting**

**Current Code** (`backend/main.py`):
```python
app.include_router(predictions.router, prefix="/api", tags=["predictions"])
```

**Route Definitions** (`backend/api/routes/predictions.py`):
```python
@router.get("/", response_model=PredictionListResponse)  # GET /api/
@router.get("/{prediction_id}", response_model=PredictionDetailResponse)  # GET /api/{prediction_id}
@router.get("/download_predictions/{prediction_id}", response_model=DownloadUrlResponse)  # GET /api/download_predictions/{prediction_id}
```

**What Happens:**
1. Frontend requests: `GET /api/predictions?user_id=...`
2. FastAPI tries to match routes:
   - `/api/` doesn't match (different path)
   - `/api/{prediction_id}` **MATCHES** with `prediction_id='predictions'`! ✅ (Wrong match!)
   - FastAPI captures `'predictions'` as the path parameter
3. Backend tries: `WHERE predictions.id = 'predictions'::UUID`
4. Database rejects: `'predictions'` is not a valid UUID

**Why This Happens:**
- The router is mounted at `/api` instead of `/api/predictions`
- FastAPI's path parameter matching is greedy
- `/{prediction_id}` matches ANY string, including `'predictions'`

---

## **✅ SOLUTION: Correct Router Mounting**

### **Change 1: Update Router Prefix**

**File:** `backend/main.py`

**Current:**
```python
app.include_router(predictions.router, prefix="/api", tags=["predictions"])
```

**Fixed:**
```python
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
```

### **Change 2: Update Router Route Definitions**

**File:** `backend/api/routes/predictions.py`

**Current Routes:**
```python
@router.get("/", ...)                              # Becomes: GET /api/predictions/
@router.get("/{prediction_id}", ...)              # Becomes: GET /api/predictions/{prediction_id}
@router.get("/download_predictions/{prediction_id}", ...)  # Becomes: GET /api/predictions/download_predictions/{prediction_id}
```

**After Fix:**
```
GET /api/predictions                               # List all predictions
GET /api/predictions/{prediction_id}              # Get prediction details
GET /api/predictions/download_predictions/{prediction_id}  # Download prediction
```

### **Change 3: Add UUID Validation**

**File:** `backend/api/routes/predictions.py`

**Add UUID Conversion** (defensive programming):
```python
import uuid as uuid_lib

@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction_detail(
    prediction_id: str,
    user_id: str = Query(..., description="User ID for ownership verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """..."""
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Convert prediction_id from string to UUID
        try:
            prediction_uuid = uuid_lib.UUID(prediction_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prediction ID format: {prediction_id}"
            )
        
        # Query prediction by ID
        stmt = select(Prediction).where(Prediction.id == prediction_uuid)
        result = await db.execute(stmt)
        # ... rest of logic
```

**Apply Same Fix to:**
- `download_prediction_results()` function (line 192)

---

## **📝 IMPLEMENTATION CHECKLIST**

### **Step 1: Update Main Router Configuration** ✅
- [x] File: `backend/main.py`
- [x] Change: `prefix="/api"` → `prefix="/api/predictions"`
- [x] Impact: All predictions routes now under `/api/predictions`

### **Step 2: Add UUID Conversion in Predictions Routes** ✅
- [x] File: `backend/api/routes/predictions.py`
- [x] Add: `import uuid as uuid_lib`
- [x] Update: `get_prediction_detail()` - convert string → UUID
- [x] Update: `download_prediction_results()` - convert string → UUID
- [x] Impact: Better error messages, prevents database type errors

### **Step 3: Verify Frontend Routes** ✅
- [x] File: `frontend/src/services/api.ts`
- [x] Check: All routes already correct (`/api/predictions`, `/api/predictions/${id}`)
- [x] Impact: No frontend changes needed

### **Step 4: Test All Predictions Endpoints** ⏳
- [ ] Test: `GET /api/predictions?user_id=...` (list)
- [ ] Test: `GET /api/predictions/{uuid}?user_id=...` (detail)
- [ ] Test: `GET /api/predictions/download_predictions/{uuid}?user_id=...` (download)

---

## **🔍 ADDITIONAL ISSUES FOUND**

### **Issue 1: Missing UUID Type Annotation**

**File:** `backend/api/routes/predictions.py`

**Problem:**
```python
prediction_id: str  # Path parameter is string, but database expects UUID
```

**Impact:** Type confusion between string and UUID

**Fix:** Add explicit type conversion (already included in Step 2)

---

### **Issue 2: No Validation for UUID Format**

**Current Code:**
```python
stmt = select(Prediction).where(Prediction.id == prediction_id)
```

**Problem:** If `prediction_id` is not a valid UUID, database throws cryptic error

**Fix:** Validate UUID format before database query (already included in Step 2)

---

### **Issue 3: Inconsistent Error Handling**

**Current:**
```python
except Exception as e:
    logger.error(f"Error retrieving prediction {prediction_id}: {str(e)}")
    raise HTTPException(
        status_code=500,
        detail="Internal server error while retrieving prediction details"
    )
```

**Problem:** Doesn't distinguish between:
- Invalid UUID format (400 Bad Request)
- Prediction not found (404 Not Found)
- Database error (500 Internal Server Error)

**Fix:** Add specific exception handling for UUID validation errors

---

## **📋 COMPLETE CODE CHANGES**

### **File 1: `backend/main.py`**

**Line 147:**
```python
# BEFORE
app.include_router(predictions.router, prefix="/api", tags=["predictions"])

# AFTER
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
```

---

### **File 2: `backend/api/routes/predictions.py`**

**Import Section (Add):**
```python
import uuid as uuid_lib
```

**Function: `get_prediction_detail()` (Lines 122-190):**

```python
@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction_detail(
    prediction_id: str,
    user_id: str = Query(..., description="User ID for ownership verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific prediction
    
    Args:
        prediction_id: UUID of the prediction
        user_id: ID of the user (for ownership verification)
        db: Database session
        
    Returns:
        Detailed prediction information
    """
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Convert and validate prediction_id
        try:
            prediction_uuid = uuid_lib.UUID(prediction_id)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prediction ID format: {prediction_id} must be a valid UUID"
            )
        
        # Query prediction by ID
        stmt = select(Prediction).where(Prediction.id == prediction_uuid)
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction with ID {prediction_id} not found"
            )
        
        # Check ownership
        if prediction.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't have permission to view this prediction"
            )
        
        # Convert to response format
        prediction_detail = PredictionDetail(
            id=str(prediction.id),
            upload_id=prediction.upload_id,
            user_id=prediction.user_id,
            status=prediction.status.value,
            s3_output_key=prediction.s3_output_key,
            rows_processed=prediction.rows_processed,
            metrics_json=prediction.metrics_json,
            error_message=prediction.error_message,
            created_at=prediction.created_at,
            updated_at=prediction.updated_at
        )
        
        logger.info(f"Retrieved prediction details for {prediction_id}, user {user_id}")
        
        return PredictionDetailResponse(
            success=True,
            prediction=prediction_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prediction {prediction_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving prediction details"
        )
```

**Function: `download_prediction_results()` (Lines 192-278):**

```python
@router.get("/download_predictions/{prediction_id}", response_model=DownloadUrlResponse)
async def download_prediction_results(
    prediction_id: str,
    user_id: str = Query(..., description="User ID for ownership verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a presigned download URL for prediction results
    
    Args:
        prediction_id: UUID of the prediction
        user_id: ID of the user (for ownership verification)
        db: Database session
        
    Returns:
        Presigned download URL
    """
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Convert and validate prediction_id
        try:
            prediction_uuid = uuid_lib.UUID(prediction_id)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prediction ID format: {prediction_id} must be a valid UUID"
            )
        
        # Query prediction by ID
        stmt = select(Prediction).where(Prediction.id == prediction_uuid)
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction with ID {prediction_id} not found"
            )
        
        # Check ownership
        if prediction.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't have permission to download this prediction"
            )
        
        # Check if prediction is completed and has output
        if prediction.status != PredictionStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Prediction is not completed (status: {prediction.status.value})"
            )
        
        if not prediction.s3_output_key:
            raise HTTPException(
                status_code=404,
                detail="No output file available for this prediction"
            )
        
        # Generate presigned URL for download
        expires_in = 600  # 10 minutes
        
        try:
            presigned_url = s3_service.generate_presigned_download_url(
                object_key=prediction.s3_output_key,
                expires_in=expires_in,
                http_method='GET',
                content_disposition=f'attachment; filename="prediction_results_{prediction_id}.csv"'
            )
            
            logger.info(f"Generated download URL for prediction {prediction_id}, user {user_id}")
            
            return DownloadUrlResponse(
                success=True,
                download_url=presigned_url,
                expires_in=expires_in
            )
            
        except Exception as s3_error:
            logger.error(f"Failed to generate presigned URL for {prediction.s3_output_key}: {str(s3_error)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate download URL"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating download URL for prediction {prediction_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating download URL"
        )
```

---

## **🧪 TESTING PLAN**

### **Step 1: Local Validation (Optional)**
```bash
# If testing locally
cd backend
pytest tests/test_predictions.py -v
```

### **Step 2: Deployment**
1. Commit changes
2. Push to GitHub
3. Wait for CI/CD (~10 minutes)
4. Verify deployment in AWS ECS

### **Step 3: Manual Testing**
1. **List Predictions:**
   - Go to: https://app.retainwiseanalytics.com/predictions
   - Expected: List of predictions displays
   - Check: Browser console shows `200 OK` for `/api/predictions`

2. **View Prediction Detail:**
   - Click on a prediction
   - Expected: Detailed view displays
   - Check: Browser console shows `200 OK` for `/api/predictions/{uuid}`

3. **Download Prediction:**
   - Click "Download" button (if prediction is COMPLETED)
   - Expected: File downloads successfully
   - Check: Browser console shows `200 OK` for `/api/predictions/download_predictions/{uuid}`

4. **Error Cases:**
   - Try invalid URL: `/api/predictions/invalid-uuid`
   - Expected: `400 Bad Request` with clear error message

---

## **📊 RISK ASSESSMENT**

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Route conflict with other endpoints** | Low | All predictions routes now properly scoped under `/api/predictions` |
| **Frontend code needs update** | Low | Frontend already uses correct paths `/api/predictions` |
| **Breaking change for existing API consumers** | Low | No external API consumers yet (B2B SaaS, authenticated only) |
| **UUID validation may reject valid old data** | Low | All existing prediction IDs in database are valid UUIDs |
| **Downstream services affected** | None | No downstream services consume predictions API |

**Overall Risk:** ✅ **LOW** - Safe to deploy

---

## **⏱️ ESTIMATED TIME**

- **Code Changes:** 15 minutes
- **Testing:** 10 minutes
- **Deployment:** 10-15 minutes
- **Verification:** 5 minutes
- **Total:** ~40-45 minutes

---

## **✅ SUCCESS CRITERIA**

1. ✅ `GET /api/predictions?user_id=...` returns 200 OK with predictions list
2. ✅ Frontend displays predictions list without errors
3. ✅ No `500 Internal Server Error` in logs
4. ✅ No `invalid UUID` errors in logs
5. ✅ Predictions page loads successfully
6. ✅ Can view individual prediction details
7. ✅ Can download completed predictions

---

## **📝 DEPLOYMENT STEPS**

1. **Commit Changes:**
   ```bash
   git add backend/main.py backend/api/routes/predictions.py
   git commit -m "fix(predictions): correct router mounting and add UUID validation"
   git push origin main
   ```

2. **Monitor Deployment:**
   - GitHub Actions: https://github.com/muhammadzeb86/churn-saas/actions
   - Expected: ✅ Build, ✅ Push to ECR, ✅ Deploy to ECS

3. **Verify in Logs:**
   ```
   ✅ GET /api/predictions 200 OK
   ✅ No UUID errors
   ```

4. **Test in Browser:**
   - Navigate to predictions page
   - Verify no errors

---

## **🔄 ROLLBACK PLAN**

If deployment fails:
1. GitHub Actions will auto-rollback (circuit breaker)
2. Manual rollback: Revert commit and push
3. Alternative: Scale service to previous task definition

**Rollback Time:** < 5 minutes

---

**Document Status:** ✅ **READY FOR IMPLEMENTATION**  
**Confidence Level:** 🟢 **HIGH** - Simple, targeted fix with low risk  
**Recommended Agent:** `composer-1` or `auto` (cost-effective for straightforward fixes)

