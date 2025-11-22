# RetainWise Analytics - Architecture & Coding Guidelines

## 🚨 CRITICAL: For All AI Coding Agents

**READ THIS FIRST before making ANY code changes to this project.**

This document outlines the core architecture and strict guidelines that MUST be followed to maintain system integrity.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Frontend-Backend Connection](#frontend-backend-connection)
4. [Authentication Flow](#authentication-flow)
5. [API Structure](#api-structure)
6. [Database Schema](#database-schema)
7. [Data Flow](#data-flow)
8. [Core Structure Rules](#core-structure-rules)
9. [Development Guidelines](#development-guidelines)

---

## 🏗️ Architecture Overview

RetainWise Analytics is a **full-stack SaaS application** for customer retention analytics with ML-powered churn prediction.

```
┌─────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │    Frontend      │  HTTPS  │     Backend      │             │
│  │   React + TS     │ ◄─────► │  FastAPI Python  │             │
│  │  (Port 3000)     │         │   (Port 8000)    │             │
│  └──────────────────┘         └──────────────────┘             │
│           │                            │                         │
│           │ Clerk JWT                  │                         │
│           ▼                            ▼                         │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Clerk Auth      │         │   PostgreSQL     │             │
│  │  (External)      │         │    Database      │             │
│  └──────────────────┘         └──────────────────┘             │
│                                        │                         │
│                                        ▼                         │
│                               ┌──────────────────┐              │
│                               │   AWS Services   │              │
│                               │  S3, SQS, RDS    │              │
│                               └──────────────────┘              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### Frontend (`/frontend/`)
- **Framework**: React 19.1.0 with TypeScript
- **Routing**: React Router DOM 7.6.1
- **Styling**: TailwindCSS 3.4.4
- **Authentication**: Clerk React 5.31.7
- **HTTP Client**: Axios 1.9.0
- **BI Integration**: PowerBI Client React 2.0.0
- **Build Tool**: React Scripts 5.0.1

### Backend (`/backend/`)
- **Framework**: FastAPI (Python)
- **Database ORM**: SQLAlchemy (AsyncIO)
- **Database**: PostgreSQL
- **Authentication**: Clerk JWT (jose library)
- **Cloud Services**: AWS (boto3)
  - S3: File storage
  - SQS: Async prediction queue
  - RDS: PostgreSQL hosting
- **ML**: scikit-learn, pandas, numpy
- **Server**: Uvicorn ASGI

### Infrastructure (`/infra/`)
- **IaC**: Terraform
- **Container**: Docker
- **Orchestration**: AWS ECS (Fargate)
- **Load Balancer**: AWS ALB
- **DNS**: Route53
- **CI/CD**: GitHub Actions

---

## 🔌 Frontend-Backend Connection

### 1. **Base URL Configuration**

Frontend communicates with backend via environment variable:

**Frontend** (`frontend/.env`):
```env
REACT_APP_BACKEND_URL=http://retainwise-alb-2130184417.us-east-1.elb.amazonaws.com
# OR in production:
# REACT_APP_BACKEND_URL=https://api.retainwiseanalytics.com
```

**Backend** (`backend/env.example`):
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@host/db
```

### 2. **API Client Setup**

Frontend uses Axios with interceptors (`frontend/src/services/api.ts`):

```typescript
const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://api.retainwiseanalytics.com';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' }
});

// Auto-inject JWT token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### 3. **CORS Configuration**

Backend explicitly allows frontend origins (`backend/main.py:99-109`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",           # Local development
        "https://retainwiseanalytics.com", # Production
        "https://www.retainwiseanalytics.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**⚠️ NEVER change these CORS settings without explicit approval.**

---

## 🔐 Authentication Flow

### Overview
RetainWise uses **Clerk** for authentication with JWT tokens.

```
┌─────────┐         ┌─────────┐         ┌─────────┐
│ Frontend│         │  Clerk  │         │ Backend │
└────┬────┘         └────┬────┘         └────┬────┘
     │                   │                    │
     │  1. User Login    │                    │
     ├──────────────────►│                    │
     │                   │                    │
     │  2. JWT Token     │                    │
     │◄──────────────────┤                    │
     │                   │                    │
     │  3. API Request + JWT Token            │
     ├───────────────────────────────────────►│
     │                   │                    │
     │                   │  4. Verify JWT     │
     │                   │◄───────────────────┤
     │                   │                    │
     │                   │  5. Valid/Invalid  │
     │                   ├───────────────────►│
     │                   │                    │
     │  6. Response (200 or 401)              │
     │◄───────────────────────────────────────┤
```

### Frontend Auth Setup

1. **Clerk Provider** wraps entire app (`frontend/src/App.tsx`):
```typescript
<ClerkProvider publishableKey={REACT_APP_CLERK_PUBLISHABLE_KEY}>
  <UserProvider>
    <Router>
      <AppRoutes />
    </Router>
  </UserProvider>
</ClerkProvider>
```

2. **Protected Routes** verify authentication:
```typescript
// frontend/src/components/auth/ProtectedRoute.tsx
const { isLoaded, isSignedIn } = useAuth();
if (!isSignedIn) return <Navigate to="/login" />;
```

3. **Token Storage**: JWT stored in `localStorage.getItem('token')`

### Backend Auth Verification

1. **Middleware** (`backend/auth/middleware.py`):
```python
async def get_current_user(credentials: HTTPAuthorizationCredentials):
    # Verify JWT token signature and expiration
    payload = verify_clerk_token(credentials.credentials)
    return user_info

def require_user_ownership(user_id_param: str, current_user: Dict):
    # Ensure user can only access their own resources
    if current_user["id"] != user_id_param:
        raise HTTPException(status_code=403)
```

2. **Route Protection**:
```python
@router.post("/upload/csv")
async def upload_csv(
    user_id: str = Form(...),
    current_user: Dict = Depends(get_current_user_dev_mode), # Validates JWT
    db: AsyncSession = Depends(get_db)
):
    require_user_ownership(user_id, current_user) # Validates ownership
```

**🔒 Security Rules:**
- NEVER bypass `get_current_user` or `require_user_ownership`
- NEVER expose user data without ownership verification
- NEVER store sensitive credentials in code

---

## 📡 API Structure

### API Endpoints Organization

Backend uses **APIRouter** pattern (`backend/main.py:112-120`):

```python
# Core business logic
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(predictions.router, prefix="/api", tags=["predictions"])
app.include_router(powerbi.router, prefix="/api", tags=["powerbi"])
app.include_router(clerk.router, prefix="/api", tags=["auth"])

# System endpoints
app.include_router(version.router, tags=["version"])
app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
```

### Complete API Reference

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| **Upload** |
| `/api/upload/csv` | POST | Upload CSV file | ✅ |
| `/api/upload/presign` | POST | Get presigned S3 URL | ✅ |
| `/api/upload/confirm-upload` | POST | Confirm client-side upload | ✅ |
| `/api/upload/files/{user_id}` | GET | Get user's uploads | ✅ |
| **Predictions** |
| `/api/predictions/` | GET | List user predictions | ✅ |
| `/api/predictions/{id}` | GET | Get prediction detail | ✅ |
| `/api/predictions/download_predictions/{id}` | GET | Download results | ✅ |
| **Auth** |
| `/api/auth/sync_user` | POST | Sync Clerk user to DB | ✅ |
| **PowerBI** |
| `/api/powerbi/embed-token` | GET | Get PowerBI embed token | ✅ |
| **System** |
| `/health` | GET | Health check | ❌ |
| `/monitoring/health` | GET | Detailed health | ❌ |
| `/monitoring/metrics` | GET | System metrics | ❌ |

### Frontend API Service

Organized by domain (`frontend/src/services/api.ts`):

```typescript
// Authentication
export const authAPI = {
  checkHealth: () => api.get('/health'),
  syncUser: (userData: any) => api.post('/auth/sync_user', userData)
};

// File uploads
export const uploadAPI = {
  getUploads: (userId: string) => api.get('/uploads', { params: { user_id: userId }}),
  uploadCSV: (formData: FormData) => api.post('/upload/csv', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
};

// ML predictions
export const predictionsAPI = {
  getPredictions: (userId: string) => api.get('/predictions', { params: { user_id: userId }}),
  getPredictionDetail: (id: string, userId: string) => api.get(`/predictions/${id}`, { params: { user_id: userId }}),
  downloadPrediction: (id: string, userId: string) => api.get(`/predictions/download_predictions/${id}`, { params: { user_id: userId }})
};

// PowerBI analytics
export const powerbiAPI = {
  getEmbedToken: () => api.get('/powerbi/embed-token')
};
```

**⚠️ API Rules:**
- NEVER create new endpoints without updating `api.ts`
- ALWAYS use existing API service functions
- NEVER hardcode API URLs in components
- ALWAYS pass `user_id` for user-scoped requests

---

## 🗄️ Database Schema

### Core Models (`backend/models.py`)

```
┌────────────────┐
│     User       │
├────────────────┤
│ id (PK)        │◄─────────┐
│ email (UNIQUE) │          │
│ clerk_id       │          │
│ full_name      │          │
│ created_at     │          │
└────────────────┘          │
                            │ 1:N
                            │
┌────────────────┐          │
│    Upload      │          │
├────────────────┤          │
│ id (PK)        │          │
│ filename       │          │
│ s3_object_key  │          │
│ user_id (FK)   ├──────────┘
│ status         │
│ upload_time    │
└────────────────┘
        │ 1:N
        │
        ▼
┌────────────────┐
│  Prediction    │
├────────────────┤
│ id (UUID, PK)  │
│ upload_id (FK) │
│ user_id (FK)   │
│ status         │◄── ENUM: QUEUED, RUNNING, COMPLETED, FAILED
│ s3_output_key  │
│ rows_processed │
│ metrics_json   │
│ error_message  │
│ created_at     │
└────────────────┘
```

### Critical Database Rules

1. **DO NOT modify schema without migration**:
   ```bash
   # Always use Alembic for schema changes
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```

2. **DO NOT delete cascade relationships** - they prevent orphaned records

3. **DO NOT change primary keys** - breaks foreign key relationships

4. **DO NOT remove indexes** - critical for query performance:
   - `users.email`, `users.clerk_id`
   - `uploads.user_id`
   - `predictions.user_id`, `predictions.upload_id`

---

## 🔄 Data Flow

### Upload & Prediction Flow

```
┌─────────┐
│ 1. User │
│ Uploads │
│  CSV    │
└────┬────┘
     │
     ▼
┌──────────────────────────────────────────────────────┐
│ Frontend: Upload.tsx                                  │
│ - Validates file (CSV, <10MB)                        │
│ - Calls uploadAPI.uploadCSV(formData)                │
└────┬─────────────────────────────────────────────────┘
     │ POST /api/upload/csv
     │ Headers: Authorization: Bearer <JWT>
     │ Body: FormData { file, user_id }
     ▼
┌──────────────────────────────────────────────────────┐
│ Backend: upload.py                                    │
│ 1. Verify JWT token ✓                                │
│ 2. Check user ownership ✓                            │
│ 3. Upload file to S3 ✓                               │
│ 4. Create Upload record in DB ✓                      │
│ 5. Create Prediction record (status=QUEUED) ✓        │
│ 6. Publish message to SQS ✓                          │
└────┬─────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────┐
│ AWS SQS Queue                                         │
│ Message: { prediction_id, upload_id, s3_key }        │
└────┬─────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────┐
│ Worker Process: workers/prediction_worker.py          │
│ 1. Poll SQS for messages                             │
│ 2. Download CSV from S3                              │
│ 3. Run ML model prediction                           │
│ 4. Upload results to S3                              │
│ 5. Update Prediction (status=COMPLETED, metrics)     │
└────┬─────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────┐
│ Frontend: Predictions.tsx                             │
│ - Polls predictionsAPI.getPredictions(userId)        │
│ - Shows status updates                               │
│ - Allows download when COMPLETED                     │
└──────────────────────────────────────────────────────┘
```

### Key Flow Points

1. **Frontend → Backend**: Always includes JWT in `Authorization` header
2. **Backend → S3**: Uses boto3 with IAM role credentials (no hardcoded keys)
3. **Backend → Database**: Uses async SQLAlchemy sessions
4. **Backend → SQS**: Publishes async prediction tasks
5. **Worker → SQS → Backend → DB**: Updates prediction status

**⚠️ Flow Rules:**
- NEVER skip authentication steps
- NEVER expose S3 keys directly (use presigned URLs)
- NEVER block user upload on prediction completion (async via SQS)
- ALWAYS validate user ownership before data access

---

## ⚙️ Core Structure Rules

### 🚨 ABSOLUTELY FORBIDDEN

**The following changes will BREAK the system. DO NOT make them:**

1. **Authentication Bypass**
   - ❌ Removing `Depends(get_current_user_dev_mode)` from routes
   - ❌ Disabling `require_user_ownership()` checks
   - ❌ Exposing user data without JWT verification

2. **CORS Modification**
   - ❌ Adding `allow_origins=["*"]` (security vulnerability)
   - ❌ Changing existing allowed origins without approval

3. **Database Schema Changes Without Migration**
   - ❌ Modifying `models.py` without running Alembic
   - ❌ Deleting columns or tables directly
   - ❌ Changing foreign key relationships

4. **Breaking API Contracts**
   - ❌ Changing endpoint URLs (breaks frontend)
   - ❌ Modifying request/response schemas without frontend updates
   - ❌ Removing query parameters that frontend relies on

5. **Environment Variables**
   - ❌ Hardcoding credentials in code
   - ❌ Committing `.env` files to git
   - ❌ Removing required environment variables

6. **File Structure Changes**
   - ❌ Moving `backend/api/routes/` files without updating imports
   - ❌ Renaming `frontend/src/services/api.ts` (central API client)
   - ❌ Deleting middleware files in `backend/middleware/`

### ✅ ALWAYS REQUIRED

**When making changes, you MUST:**

1. **Adding New API Endpoints**
   ```python
   # 1. Create route in backend/api/routes/
   # 2. Add authentication dependency
   # 3. Include router in backend/main.py
   # 4. Update frontend/src/services/api.ts
   # 5. Test with valid JWT token
   ```

2. **Modifying Database Schema**
   ```bash
   # 1. Edit backend/models.py
   alembic revision --autogenerate -m "Add new field"
   alembic upgrade head
   # 2. Update Pydantic schemas in backend/schemas/
   # 3. Update frontend TypeScript types
   ```

3. **Adding Frontend Components**
   ```typescript
   // 1. Create component in frontend/src/components/ or pages/
   // 2. Use existing API services from api.ts
   // 3. Wrap data-fetching routes with ProtectedRoute
   // 4. Handle loading and error states
   ```

4. **Changing API Request/Response**
   ```python
   # 1. Update Pydantic model in backend/schemas/
   # 2. Update route handler
   # 3. Update frontend TypeScript interface
   # 4. Update API service function in api.ts
   # 5. Update calling components
   ```

---

## 🔧 Development Guidelines

### Local Development Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env  # Configure DATABASE_URL, AWS credentials
alembic upgrade head  # Run migrations
python main.py  # Runs on http://localhost:8000
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env  # Configure REACT_APP_CLERK_PUBLISHABLE_KEY, REACT_APP_BACKEND_URL
npm start  # Runs on http://localhost:3000
```

### Testing Guidelines

1. **Always test authentication flow**:
   - Login via `/login`
   - Verify JWT token in browser DevTools → Application → Local Storage
   - Test protected routes redirect when not authenticated

2. **Test API endpoints**:
   ```bash
   # With valid JWT token
   curl -H "Authorization: Bearer <token>" http://localhost:8000/api/predictions?user_id=<user_id>
   ```

3. **Test file upload**:
   - Upload CSV file through frontend
   - Verify Upload record in database
   - Verify Prediction record created with QUEUED status
   - Check S3 bucket for uploaded file

### Code Style

**Python (Backend):**
- Follow PEP 8
- Use type hints: `def func(param: str) -> Dict[str, Any]:`
- Async functions: `async def` with `await`
- Error handling: Raise `HTTPException` with appropriate status codes

**TypeScript (Frontend):**
- Use functional components with hooks
- Type all props and state: `interface Props { ... }`
- Error boundaries for async operations
- Use `useAuth()` hook for authentication state

### Logging

**Backend logging levels:**
```python
logger.info("Normal operation")
logger.warning("Recoverable issue")
logger.error("Failed operation")
```

**Frontend error handling:**
```typescript
try {
  const response = await api.get('/endpoint');
} catch (error) {
  console.error('Operation failed:', error);
  // Show user-friendly error message
}
```

---

## 📝 Summary Checklist for AI Agents

Before making ANY changes, verify:

- [ ] I understand the frontend-backend connection (Axios + FastAPI)
- [ ] I will NOT modify CORS settings
- [ ] I will NOT bypass authentication checks
- [ ] I will NOT change API endpoints without updating frontend
- [ ] I will NOT modify database schema without Alembic migration
- [ ] I will use existing API service functions in `api.ts`
- [ ] I will include JWT token in all authenticated requests
- [ ] I will verify user ownership for user-scoped data
- [ ] I will test my changes with actual authentication flow
- [ ] I will NOT commit environment files or credentials

**When in doubt, ASK before making structural changes.**

---

## 📞 Questions?

If you need clarification on any architectural decisions or need to make changes that might affect core structure:

1. **Check existing code** for similar patterns
2. **Read backend/README.md** and route-specific documentation
3. **Test thoroughly** in development environment before production
4. **Document changes** if adding new features

---

**Last Updated**: 2025-10-19  
**Project**: RetainWise Analytics  
**Version**: 2.0.0
