# RetainWise Analytics - AI Agent Quick Reference

**⚡ Copy and paste this into new AI coding sessions**

---

## 🏗️ System Architecture

**Frontend**: React + TypeScript (Port 3000) → **Backend**: FastAPI + Python (Port 8000) → **Database**: PostgreSQL  
**Auth**: Clerk JWT → **Storage**: AWS S3 → **Queue**: AWS SQS → **BI**: PowerBI

---

## 📂 Project Structure

```
/frontend/          # React TypeScript SPA
  /src/
    /services/
      api.ts        # ⚠️ ALL API calls go through here
    /pages/         # Dashboard, Upload, Predictions
    /components/
      /auth/        # ProtectedRoute wrapper
    App.tsx         # Clerk auth wrapper, routing
    
/backend/           # FastAPI Python
  main.py           # ⚠️ App entry, CORS config, route registration
  /api/
    /routes/        # upload.py, predictions.py, powerbi.py, clerk.py
  /auth/
    middleware.py   # ⚠️ JWT verification, user ownership checks
  /models.py        # ⚠️ SQLAlchemy models (User, Upload, Prediction)
  /core/
    config.py       # Environment variables
  /services/        # s3_service.py, sqs_service.py
```

---

## 🔌 Frontend → Backend Connection

1. **API Client** (`frontend/src/services/api.ts`):
   ```typescript
   const API_URL = process.env.REACT_APP_BACKEND_URL;
   const api = axios.create({ baseURL: API_URL });
   
   // Auto-injects JWT token from localStorage
   api.interceptors.request.use((config) => {
     config.headers.Authorization = `Bearer ${localStorage.getItem('token')}`;
   });
   ```

2. **Environment Variables**:
   - Frontend: `REACT_APP_BACKEND_URL`, `REACT_APP_CLERK_PUBLISHABLE_KEY`
   - Backend: `DATABASE_URL`, `AWS_REGION`, `S3_BUCKET`, `PREDICTIONS_QUEUE_URL`

3. **CORS Whitelist** (`backend/main.py:99-109`):
   ```python
   allow_origins=[
     "http://localhost:3000",
     "https://retainwiseanalytics.com",
     "https://www.retainwiseanalytics.com"
   ]
   ```

---

## 🔐 Authentication Flow

```
User Login → Clerk → JWT Token → Frontend (localStorage)
                                     ↓
                          API Request + JWT in Authorization header
                                     ↓
                          Backend verifies JWT (auth/middleware.py)
                                     ↓
                          Check user ownership → Allow/Deny
```

**All protected routes use**:
```python
async def route(
    user_id: str,
    current_user: Dict = Depends(get_current_user_dev_mode),
    db: AsyncSession = Depends(get_db)
):
    require_user_ownership(user_id, current_user)
```

---

## 📡 API Endpoints Reference

| Endpoint | Method | Frontend Function | Auth |
|----------|--------|-------------------|------|
| `/api/upload/csv` | POST | `uploadAPI.uploadCSV(formData)` | ✅ |
| `/api/predictions` | GET | `predictionsAPI.getPredictions(userId)` | ✅ |
| `/api/predictions/{id}` | GET | `predictionsAPI.getPredictionDetail(id, userId)` | ✅ |
| `/api/predictions/download_predictions/{id}` | GET | `predictionsAPI.downloadPrediction(id, userId)` | ✅ |
| `/api/powerbi/embed-token` | GET | `powerbiAPI.getEmbedToken()` | ✅ |
| `/health` | GET | `authAPI.checkHealth()` | ❌ |

---

## 🗄️ Database Models

```python
User (id, email, clerk_id, full_name)
  ↓ 1:N
Upload (id, filename, s3_object_key, user_id, status)
  ↓ 1:N  
Prediction (id UUID, upload_id, user_id, status, s3_output_key, metrics_json)
  # status: QUEUED → RUNNING → COMPLETED/FAILED
```

---

## 🚨 CRITICAL RULES - DO NOT VIOLATE

### ❌ ABSOLUTELY FORBIDDEN

1. **Authentication**:
   - ❌ Remove `Depends(get_current_user_dev_mode)` from routes
   - ❌ Skip `require_user_ownership()` checks
   - ❌ Expose user data without JWT verification

2. **CORS**:
   - ❌ Add `allow_origins=["*"]`
   - ❌ Modify allowed origins without approval

3. **Database**:
   - ❌ Change schema without Alembic migration
   - ❌ Delete foreign key relationships
   - ❌ Modify primary keys

4. **API**:
   - ❌ Change endpoint URLs without updating `frontend/src/services/api.ts`
   - ❌ Modify request/response schemas without updating both frontend & backend
   - ❌ Remove query parameters that frontend uses

5. **Security**:
   - ❌ Hardcode credentials in code
   - ❌ Commit `.env` files
   - ❌ Expose AWS keys directly (use presigned URLs)

### ✅ REQUIRED PATTERNS

#### Adding New API Endpoint
```python
# 1. backend/api/routes/new_route.py
@router.post("/new-endpoint")
async def new_endpoint(
    user_id: str,
    current_user: Dict = Depends(get_current_user_dev_mode),
    db: AsyncSession = Depends(get_db)
):
    require_user_ownership(user_id, current_user)
    # ... logic

# 2. backend/main.py
app.include_router(new_route.router, prefix="/api", tags=["new"])

# 3. frontend/src/services/api.ts
export const newAPI = {
  callEndpoint: (userId: string) => api.post('/new-endpoint', { user_id: userId })
};
```

#### Database Schema Change
```bash
# 1. Edit backend/models.py
# 2. Create migration
alembic revision --autogenerate -m "Add new field"
# 3. Apply migration
alembic upgrade head
# 4. Update Pydantic schemas in backend/schemas/
# 5. Update frontend TypeScript types
```

#### Adding Frontend Component
```typescript
// 1. Create in frontend/src/components/ or /pages/
// 2. Import API service
import { predictionsAPI } from '../services/api';

// 3. Wrap route with authentication
<Route path="/new-page" element={
  <ProtectedRoute>
    <Layout><NewPage /></Layout>
  </ProtectedRoute>
} />

// 4. Use API service in component
const { user } = useUser();
const data = await predictionsAPI.getPredictions(user.id);
```

---

## 🔄 Data Flow Example: CSV Upload

```
1. Frontend: User uploads CSV via Upload.tsx
   ↓ POST /api/upload/csv (FormData + JWT)
   
2. Backend: upload.py receives request
   ↓ Verify JWT → Check ownership → Validate CSV
   
3. Backend: Upload file to S3
   ↓ Create Upload record in DB
   ↓ Create Prediction record (status=QUEUED)
   
4. Backend: Publish to SQS queue
   ↓ Return response to frontend
   
5. Worker: Polls SQS → Downloads CSV → Runs ML model
   ↓ Uploads results to S3
   ↓ Updates Prediction (status=COMPLETED)
   
6. Frontend: Predictions.tsx polls API
   ↓ Shows updated status
   ↓ Allows download when COMPLETED
```

---

## 🔧 Common Tasks

### Test Authentication Locally
```bash
# 1. Start backend
cd backend && python main.py  # Port 8000

# 2. Start frontend  
cd frontend && npm start  # Port 3000

# 3. Login via http://localhost:3000/login
# 4. Check DevTools → Application → Local Storage for JWT token
# 5. Test API with token:
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/predictions?user_id=<user_id>
```

### Debug API Connection Issues
1. Check `REACT_APP_BACKEND_URL` in frontend/.env
2. Verify CORS whitelist in backend/main.py
3. Confirm JWT token in request headers (DevTools → Network)
4. Check backend logs for authentication errors

### Verify Database Changes
```bash
# Check current schema
alembic current

# View migration history
alembic history

# Rollback if needed
alembic downgrade -1
```

---

## 📝 Pre-Change Checklist

Before making changes, answer these:

- [ ] Do I need to modify API endpoints? → Update both backend route AND frontend api.ts
- [ ] Do I need to change database? → Create Alembic migration first
- [ ] Do I need user data? → Include JWT verification and ownership check
- [ ] Do I need to access S3? → Use s3_service.py, not direct boto3 calls
- [ ] Am I adding new routes? → Register in main.py, wrap with ProtectedRoute
- [ ] Am I modifying authentication? → **STOP and ask first**
- [ ] Am I changing CORS? → **STOP and ask first**

---

## 🎯 Key Files Reference

| File | Purpose | Modify With Caution |
|------|---------|---------------------|
| `backend/main.py` | App entry, CORS, route registration | ⚠️ High |
| `backend/auth/middleware.py` | JWT verification, user ownership | ⚠️ Critical |
| `backend/models.py` | Database schema | ⚠️ Critical (requires migration) |
| `frontend/src/services/api.ts` | Central API client | ⚠️ High |
| `frontend/src/App.tsx` | Routing, Clerk wrapper | ⚠️ High |
| `backend/api/routes/*` | API endpoints | ✅ Safe to extend |
| `frontend/src/pages/*` | Frontend pages | ✅ Safe to modify |
| `frontend/src/components/*` | React components | ✅ Safe to modify |

---

## 💡 When in Doubt

1. **Check existing patterns**: Look for similar implementations in codebase
2. **Read full docs**: See `ARCHITECTURE_AND_GUIDELINES.md` for details
3. **Test locally**: Always test with actual authentication flow
4. **Ask first**: If changing core structure (auth, CORS, DB schema, API contracts)

---

**Project**: RetainWise Analytics v2.0.0  
**Stack**: React + FastAPI + PostgreSQL + AWS  
**Auth**: Clerk JWT  
**Last Updated**: 2025-10-19
