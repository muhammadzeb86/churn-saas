# 🔧 **PHASE 2: PRODUCTION HARDENING - IMPLEMENTATION PLAN**

**Date:** December 10, 2025  
**Status:** Starting Phase 2  
**Timeline:** 32 hours (4-5 days)  
**Goal:** Bulletproof backend before building dashboard

---

## **📋 OVERVIEW**

### **Why Phase 2 Now?**
- ✅ Phase 1 complete - ML pipeline working end-to-end
- ✅ Phase 3.5 complete - Infrastructure automated with Terraform
- 🎯 Need stable, tested backend before Phase 4 (Dashboard/Frontend)
- 🎯 Prevent production issues before customer launch

### **Success Criteria**
1. ✅ 200+ comprehensive tests with 95%+ coverage
2. ✅ <100ms API response times (P95)
3. ✅ <50ms database query times
4. ✅ Production-grade security audit complete
5. ✅ Complete Swagger/OpenAPI documentation
6. ✅ User-friendly error messages throughout

---

## **🎯 TASK BREAKDOWN**

### **Task 2.1: Comprehensive Testing Suite (8 hours)**

**Goal:** Increase test coverage from 85% to 95%+, reach 200+ total tests

**Current State:**
- ✅ 149 tests passing
- ✅ ~85% coverage
- ✅ Key components tested: column mapper, feature validator, simple explainer, monitoring, auth

**What's Missing:**
- Integration tests (end-to-end pipeline)
- Load tests (1000+ row CSVs)
- Security tests (JWT edge cases, input validation)
- Error scenario tests (S3 failures, DB timeouts, SQS failures)
- Performance tests (response time SLAs)
- Edge case tests (empty CSVs, malformed data, special characters)

**Implementation Plan:**

#### **2.1.1: Integration Tests (3 hours)**
Create `tests/integration/` directory with:

1. **test_end_to_end_pipeline.py**
   - Upload CSV → SQS → Worker → Prediction → S3 → Download
   - Test with both Telecom and SaaS baseline models
   - Verify explanation generation for both models
   - Test data collection (ml_training_data table)

2. **test_saas_baseline_integration.py**
   - End-to-end SaaS baseline predictions
   - Verify risk_factors and protective_factors
   - Verify explanation generation from factors
   - Verify JSON formatting in CSV output

3. **test_error_recovery.py**
   - S3 upload failures → graceful error handling
   - Database connection failures → retry logic
   - SQS message failures → DLQ routing
   - Model loading failures → fallback behavior

#### **2.1.2: Load & Performance Tests (2 hours)**
Create `tests/performance/` directory with:

1. **test_large_csvs.py**
   - 1,000 row CSV processing time
   - 10,000 row CSV processing time
   - Memory usage tracking
   - Throughput metrics (rows/second)

2. **test_concurrent_predictions.py**
   - Multiple predictions in parallel
   - SQS queue handling under load
   - Database connection pool behavior
   - Worker scaling behavior

#### **2.1.3: Security Tests (2 hours)**
Create `tests/security/` directory with:

1. **test_jwt_edge_cases.py**
   - Expired tokens
   - Invalid signatures
   - Missing claims
   - Token tampering attempts

2. **test_input_validation.py**
   - CSV injection attempts
   - SQL injection prevention (verify ORM protection)
   - File size limits
   - File type validation
   - Special characters in filenames
   - Path traversal attempts

3. **test_rate_limiting.py**
   - Rate limit enforcement
   - User-specific rate limits
   - API endpoint coverage

#### **2.1.4: Edge Case Tests (1 hour)**
Add to existing test files:

1. **test_edge_cases.py**
   - Empty CSVs
   - Single row CSVs
   - CSVs with missing columns
   - CSVs with extra columns
   - CSVs with special characters
   - CSVs with unicode characters
   - Very long customer IDs
   - Negative values in numeric fields

**Deliverables:**
- [ ] 200+ total tests passing
- [ ] 95%+ code coverage
- [ ] Coverage report generated (HTML)
- [ ] All critical paths tested
- [ ] All edge cases covered

---

### **Task 2.2: Database Optimization (6 hours)**

**Goal:** 10x faster queries, proper connection pooling, <50ms query times

**Current State:**
- ✅ PostgreSQL 15 on RDS
- ✅ 4 tables: users, uploads, predictions, ml_training_data
- ⚠️ Missing indexes on frequently queried columns
- ⚠️ Connection pooling may not be optimized
- ⚠️ Some queries use SELECT *

**Implementation Plan:**

#### **2.2.1: Add Database Indexes (2 hours)**

**Analyze Query Patterns:**
1. `predictions` table:
   - Frequently filtered by `user_id`
   - Frequently filtered by `status`
   - Frequently ordered by `created_at`
   - Frequently joined with `uploads` via `upload_id`

2. `uploads` table:
   - Frequently filtered by `user_id`
   - Frequently ordered by `created_at`
   - Frequently filtered by `status`

3. `ml_training_data` table:
   - Frequently filtered by `user_id`
   - Frequently filtered by `experiment_group`
   - Frequently filtered by `actual_churn` (when not null)
   - Frequently ordered by `created_at`

**Indexes to Create:**
```sql
-- Predictions table
CREATE INDEX idx_predictions_user_id ON predictions(user_id);
CREATE INDEX idx_predictions_status ON predictions(status);
CREATE INDEX idx_predictions_created_at ON predictions(created_at DESC);
CREATE INDEX idx_predictions_upload_id ON predictions(upload_id);
CREATE INDEX idx_predictions_user_status ON predictions(user_id, status);

-- Uploads table
CREATE INDEX idx_uploads_user_id ON uploads(user_id);
CREATE INDEX idx_uploads_status ON uploads(status);
CREATE INDEX idx_uploads_created_at ON uploads(created_at DESC);
CREATE INDEX idx_uploads_user_status ON uploads(user_id, status);

-- ML Training Data table
CREATE INDEX idx_ml_training_user_id ON ml_training_data(user_id);
CREATE INDEX idx_ml_training_experiment_group ON ml_training_data(experiment_group);
CREATE INDEX idx_ml_training_actual_churn ON ml_training_data(actual_churn) WHERE actual_churn IS NOT NULL;
CREATE INDEX idx_ml_training_created_at ON ml_training_data(created_at DESC);
```

**Implementation:**
- Create Alembic migration: `add_performance_indexes.py`
- Test query performance before/after indexes
- Document expected performance improvements

#### **2.2.2: Optimize Connection Pooling (2 hours)**

**Current Issue:**
- Default pool_size may be too small or too large
- No explicit pool configuration for asyncpg
- Potential connection leaks

**Fix:**
```python
# backend/api/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = settings.DATABASE_URL

# Optimized connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,           # Number of permanent connections
    max_overflow=20,        # Additional connections when pool exhausted
    pool_timeout=30,        # Seconds to wait for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Verify connection before using
)
```

**Configuration Reasoning:**
- `pool_size=10`: Sufficient for typical load (1-2 workers)
- `max_overflow=20`: Handle traffic spikes
- `pool_timeout=30`: Fail fast if pool exhausted
- `pool_recycle=3600`: Prevent stale connections
- `pool_pre_ping=True`: Catch dead connections early

**Testing:**
- Monitor connection count under load
- Test behavior when pool exhausted
- Verify no connection leaks

#### **2.2.3: Query Optimization (2 hours)**

**Current Issues:**
- Some routes use `SELECT *` (fetches unnecessary columns)
- N+1 query problems possible
- Missing query limits on list endpoints

**Optimizations:**

1. **Select Specific Columns:**
```python
# Before
predictions = await session.execute(
    select(Prediction).where(Prediction.user_id == user_id)
)

# After
predictions = await session.execute(
    select(
        Prediction.id,
        Prediction.status,
        Prediction.created_at,
        Prediction.rows_processed
    ).where(Prediction.user_id == user_id)
)
```

2. **Add Pagination Limits:**
```python
# All list endpoints should have limits
predictions = await session.execute(
    select(Prediction)
    .where(Prediction.user_id == user_id)
    .order_by(Prediction.created_at.desc())
    .limit(100)  # Prevent fetching thousands of rows
    .offset(skip)
)
```

3. **Use Eager Loading (avoid N+1):**
```python
# If we need upload data with predictions
predictions = await session.execute(
    select(Prediction)
    .options(selectinload(Prediction.upload))
    .where(Prediction.user_id == user_id)
)
```

**Files to Update:**
- `backend/api/routes/predictions.py`
- `backend/api/routes/upload.py`
- Any other routes fetching database records

**Deliverables:**
- [ ] All indexes created via Alembic migration
- [ ] Connection pooling optimized
- [ ] All queries use specific column selection
- [ ] All list endpoints have pagination limits
- [ ] Query performance benchmarks documented
- [ ] <50ms query times verified

---

### **Task 2.3: API Performance Optimization (4 hours)**

**Goal:** <100ms API response times (P95 latency)

**Current State:**
- ✅ FastAPI backend with async/await
- ⚠️ No response caching
- ⚠️ No response compression
- ⚠️ No CDN for static assets

**Implementation Plan:**

#### **2.3.1: Response Caching (2 hours)**

**What to Cache:**
1. Sample CSV downloads (static files)
2. User profile data (short TTL)
3. Prediction results (immutable once complete)

**Implementation:**
```python
# backend/middleware/cache.py
from functools import lru_cache
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib

class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Simple in-memory cache for GET responses."""
    
    def __init__(self, app, ttl: int = 300):
        super().__init__(app)
        self.cache = {}
        self.ttl = ttl
    
    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)
        
        # Generate cache key
        cache_key = f"{request.url.path}:{request.url.query}"
        
        # Check cache
        if cache_key in self.cache:
            cached_response, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                return cached_response
        
        # Process request
        response = await call_next(request)
        
        # Cache successful responses
        if response.status_code == 200:
            self.cache[cache_key] = (response, time.time())
        
        return response
```

**Add to main.py:**
```python
from backend.middleware.cache import ResponseCacheMiddleware

app.add_middleware(ResponseCacheMiddleware, ttl=300)  # 5 minute cache
```

#### **2.3.2: Response Compression (1 hour)**

**Implementation:**
```python
# backend/main.py
from fastapi.middleware.gzip import GZIPMiddleware

app.add_middleware(GZIPMiddleware, minimum_size=1000)  # Compress responses >1KB
```

**Benefits:**
- Reduce response size by 60-80%
- Faster transfer over network
- Lower bandwidth costs

#### **2.3.3: Async I/O Optimization (1 hour)**

**Current Issues:**
- Possible blocking I/O calls
- S3 operations may not be fully async

**Optimizations:**
1. **Verify All I/O is Async:**
   - Database calls: ✅ Already async (asyncpg)
   - S3 operations: ⚠️ Verify boto3 is async (use aioboto3 if needed)
   - SQS operations: ⚠️ Verify async

2. **Batch Operations:**
   - Upload multiple files to S3 in parallel
   - Fetch multiple predictions in single query

**Review Files:**
- `backend/services/s3_service.py`
- `backend/workers/prediction_worker.py`

**Deliverables:**
- [ ] Response caching implemented
- [ ] Response compression enabled
- [ ] All I/O operations verified async
- [ ] <100ms P95 latency verified
- [ ] Performance benchmarks documented

---

### **Task 2.4: Error Handling Enhancement (4 hours)**

**Goal:** User-friendly error messages, standardized responses, retry logic

**Current State:**
- ✅ Global error handler exists
- ⚠️ Error messages may be too technical
- ⚠️ No standardized error codes
- ⚠️ Limited retry logic for transient errors

**Implementation Plan:**

#### **2.4.1: Standardized Error Responses (2 hours)**

**Error Code System:**
```python
# backend/core/errors.py
from enum import Enum

class ErrorCode(str, Enum):
    # Upload errors (1000-1099)
    UPLOAD_INVALID_FILE = "ERR-1001"
    UPLOAD_FILE_TOO_LARGE = "ERR-1002"
    UPLOAD_INVALID_FORMAT = "ERR-1003"
    UPLOAD_MISSING_COLUMNS = "ERR-1004"
    
    # Prediction errors (1100-1199)
    PREDICTION_NOT_FOUND = "ERR-1101"
    PREDICTION_FAILED = "ERR-1102"
    PREDICTION_TIMEOUT = "ERR-1103"
    
    # Authentication errors (1200-1299)
    AUTH_INVALID_TOKEN = "ERR-1201"
    AUTH_EXPIRED_TOKEN = "ERR-1202"
    AUTH_MISSING_TOKEN = "ERR-1203"
    
    # Validation errors (1300-1399)
    VALIDATION_MISSING_FIELD = "ERR-1301"
    VALIDATION_INVALID_VALUE = "ERR-1302"
    VALIDATION_OUT_OF_RANGE = "ERR-1303"
    
    # System errors (1500-1599)
    SYSTEM_DATABASE_ERROR = "ERR-1501"
    SYSTEM_S3_ERROR = "ERR-1502"
    SYSTEM_SQS_ERROR = "ERR-1503"
    SYSTEM_INTERNAL_ERROR = "ERR-1500"


class ApplicationError(Exception):
    """Base exception for application errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = 500,
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Specific error classes
class UploadError(ApplicationError):
    pass

class PredictionError(ApplicationError):
    pass

class ValidationError(ApplicationError):
    pass
```

**Standardized Error Response:**
```python
{
    "error": {
        "code": "ERR-1001",
        "message": "Invalid file format. Please upload a CSV file.",
        "details": {
            "filename": "data.xlsx",
            "allowed_formats": ["csv"]
        },
        "support_url": "https://docs.retainwiseanalytics.com/errors/ERR-1001"
    }
}
```

#### **2.4.2: User-Friendly Error Messages (1 hour)**

**Technical → User-Friendly:**

| Technical | User-Friendly |
|-----------|---------------|
| "KeyError: 'customerID'" | "Missing required column 'Customer ID'. Please ensure your CSV contains this column." |
| "Connection pool limit exceeded" | "Our service is experiencing high traffic. Please try again in a moment." |
| "S3 PutObject failed" | "Failed to save your file. Please try uploading again." |
| "JWKS fetch failed" | "Authentication service temporarily unavailable. Please refresh the page." |

**Implementation:**
```python
# backend/middleware/error_handler.py
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.core.errors import ApplicationError, ErrorCode
import logging

logger = logging.getLogger(__name__)

async def application_error_handler(request: Request, exc: ApplicationError):
    """Handle application errors with user-friendly messages."""
    
    logger.error(
        f"Application error: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "support_url": f"https://docs.retainwiseanalytics.com/errors/{exc.error_code}"
            }
        }
    )
```

#### **2.4.3: Retry Logic for Transient Errors (1 hour)**

**Add Retry Decorator:**
```python
# backend/utils/retry.py
import asyncio
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def retry_async(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """Retry decorator for async functions."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {current_delay}s delay. Error: {e}"
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    return decorator
```

**Apply to Transient Operations:**
```python
# backend/services/s3_service.py
from backend.utils.retry import retry_async

class S3Service:
    @retry_async(max_retries=3, delay=1, exceptions=(ClientError,))
    async def upload_file(self, file_path: str, s3_key: str):
        # S3 upload logic
        pass
```

**Deliverables:**
- [ ] Standardized error codes defined
- [ ] User-friendly error messages implemented
- [ ] Retry logic added for transient errors
- [ ] Error handling documented
- [ ] Error response format standardized

---

### **Task 2.5: Security Audit (6 hours)**

**Goal:** Production-grade security review and hardening

**Implementation Plan:**

#### **2.5.1: Input Validation Review (2 hours)**

**Areas to Review:**
1. **File Upload Security:**
   - File size limits enforced?
   - File type validation (CSV only)?
   - Filename sanitization (prevent path traversal)?
   - File content validation (not just extension)?

2. **CSV Injection Prevention:**
   - Cells starting with `=`, `+`, `@`, `-` (formula injection)?
   - Special characters in customer IDs?
   - Max row limits?

3. **API Parameter Validation:**
   - All required fields validated?
   - Data types validated?
   - Range checks on numeric fields?
   - String length limits?

**Implementation:**
```python
# backend/utils/validation.py
import re
from pathlib import Path

DANGEROUS_PREFIXES = ['=', '+', '@', '-', '|', '%']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_ROWS = 100000

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    # Remove path components
    filename = Path(filename).name
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '_', filename)
    return filename

def validate_csv_cell(value: str) -> str:
    """Prevent CSV injection."""
    if value and value[0] in DANGEROUS_PREFIXES:
        return "'" + value  # Prepend with single quote to neutralize
    return value

def validate_file_upload(file) -> tuple[bool, str]:
    """Validate uploaded file."""
    # Check file size
    if file.size > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB"
    
    # Check file extension
    if not file.filename.endswith('.csv'):
        return False, "Only CSV files are allowed"
    
    # Check filename
    sanitized = sanitize_filename(file.filename)
    if sanitized != file.filename:
        return False, "Filename contains invalid characters"
    
    return True, ""
```

#### **2.5.2: SQL Injection Prevention Verification (1 hour)**

**Current Protection:**
- ✅ SQLAlchemy ORM (no raw SQL)
- ⚠️ Verify no raw queries anywhere

**Audit:**
```bash
# Search for potential SQL injection points
grep -r "execute.*%" backend/
grep -r "text\(" backend/
grep -r "raw_sql" backend/
```

**Expected Result:** No raw SQL queries found (all use ORM)

#### **2.5.3: PII Handling in Logs (1 hour)**

**Current Issues:**
- Customer data may be logged
- Email addresses in logs
- PII in CloudWatch metrics

**Fix:**
```python
# backend/utils/logging.py
import re
import hashlib

def sanitize_for_logging(data: dict) -> dict:
    """Remove PII from log data."""
    pii_fields = [
        'email', 'phone', 'ssn', 'address',
        'credit_card', 'customerID'
    ]
    
    sanitized = data.copy()
    for field in pii_fields:
        if field in sanitized:
            # Hash instead of removing
            value = sanitized[field]
            hashed = hashlib.sha256(str(value).encode()).hexdigest()[:8]
            sanitized[field] = f"***{hashed}"
    
    return sanitized
```

**Apply to All Logging:**
```python
logger.info(
    "Processing prediction",
    extra=sanitize_for_logging({
        "customer_id": customer_id,
        "email": email
    })
)
```

#### **2.5.4: CORS Configuration Review (1 hour)**

**Current State:**
```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Too permissive!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix:**
```python
# Only allow frontend domain
ALLOWED_ORIGINS = [
    "https://retainwiseanalytics.com",
    "https://www.retainwiseanalytics.com"
]

if settings.ENVIRONMENT == "development":
    ALLOWED_ORIGINS.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

#### **2.5.5: Rate Limiting Review (1 hour)**

**Current State:**
- ✅ Rate limiter middleware exists
- ⚠️ Verify coverage on all endpoints
- ⚠️ Verify rate limits are appropriate

**Configuration:**
```python
# backend/middleware/rate_limiter.py

# Current limits
RATE_LIMITS = {
    "default": "100/minute",
    "upload": "10/minute",      # More restrictive for expensive operations
    "predict": "20/minute",
    "download": "50/minute"
}
```

**Verify:**
- All endpoints have rate limits?
- Limits appropriate for expected usage?
- Rate limit headers returned?
- 429 Too Many Requests response?

**Deliverables:**
- [ ] Input validation comprehensive
- [ ] CSV injection prevention verified
- [ ] SQL injection prevention verified
- [ ] PII sanitization in logs
- [ ] CORS properly configured
- [ ] Rate limiting verified
- [ ] Security audit report documented

---

### **Task 2.6: API Documentation (4 hours)**

**Goal:** Complete Swagger/OpenAPI documentation for frontend team

**Implementation Plan:**

#### **2.6.1: OpenAPI Schema Generation (2 hours)**

**FastAPI Auto-Documentation:**
FastAPI automatically generates OpenAPI schema, but we need to enhance it.

**Enhancements:**
```python
# backend/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="RetainWise Analytics API",
    description="SaaS churn prediction platform API",
    version="1.0.0",
    contact={
        "name": "RetainWise Support",
        "email": "support@retainwiseanalytics.com",
        "url": "https://retainwiseanalytics.com"
    },
    license_info={
        "name": "Proprietary"
    }
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="RetainWise Analytics API",
        version="1.0.0",
        description="""
        ## Overview
        RetainWise Analytics API provides SaaS churn prediction using ML models.
        
        ## Authentication
        All endpoints require JWT authentication via Clerk.
        Include `Authorization: Bearer <token>` header in requests.
        
        ## Rate Limiting
        - Default: 100 requests/minute
        - Upload: 10 requests/minute
        - Predict: 20 requests/minute
        
        ## Error Codes
        See https://docs.retainwiseanalytics.com/errors for full list.
        """,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ClerkJWT": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Apply security globally
    openapi_schema["security"] = [{"ClerkJWT": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

#### **2.6.2: Endpoint Documentation (2 hours)**

**Add Detailed Descriptions to Routes:**
```python
# backend/api/routes/upload.py
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel, Field

class UploadResponse(BaseModel):
    upload_id: int = Field(..., description="Unique identifier for the upload")
    filename: str = Field(..., description="Name of the uploaded file")
    status: str = Field(..., description="Upload status: pending, processing, completed, failed")
    row_count: int = Field(..., description="Number of rows in the CSV")
    
    class Config:
        schema_extra = {
            "example": {
                "upload_id": 123,
                "filename": "customers.csv",
                "status": "completed",
                "row_count": 1500
            }
        }

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload Customer CSV",
    description="""
    Upload a CSV file containing customer data for churn prediction.
    
    ## Requirements
    - File format: CSV only
    - Max size: 50MB
    - Required columns: customerID, tenure, MonthlyCharges, TotalCharges, Contract
    - Optional columns: seats_used, feature_usage_score, last_activity_days_ago, support_tickets
    
    ## Process
    1. File is validated for format and required columns
    2. File is uploaded to S3
    3. Prediction job is queued for processing
    4. Returns upload_id for tracking progress
    
    ## Errors
    - ERR-1001: Invalid file format
    - ERR-1002: File too large
    - ERR-1004: Missing required columns
    """,
    responses={
        200: {"description": "File uploaded successfully"},
        400: {"description": "Invalid file or missing columns"},
        413: {"description": "File too large"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    tags=["Uploads"]
)
async def upload_csv(file: UploadFile = File(...)):
    pass
```

**Document All Endpoints:**
1. `POST /upload` - Upload CSV
2. `GET /predictions/{prediction_id}` - Get prediction status
3. `GET /predictions/{prediction_id}/download` - Download results
4. `GET /predictions` - List user's predictions
5. `GET /health` - Health check
6. `GET /csv-samples/saas` - Download SaaS sample CSV
7. `GET /csv-samples/telecom` - Download Telecom sample CSV

**Deliverables:**
- [ ] OpenAPI schema enhanced
- [ ] All endpoints documented
- [ ] Request/response examples provided
- [ ] Error codes documented
- [ ] Authentication documented
- [ ] Swagger UI accessible at `/docs`
- [ ] ReDoc accessible at `/redoc`

---

## **📊 SUCCESS METRICS**

### **Testing (Task 2.1)**
- ✅ 200+ tests passing
- ✅ 95%+ code coverage
- ✅ All integration tests passing
- ✅ All security tests passing
- ✅ Load tests passing (1000+ rows)

### **Database (Task 2.2)**
- ✅ All indexes created
- ✅ Query times <50ms (verified)
- ✅ Connection pooling optimized
- ✅ No connection leaks

### **Performance (Task 2.3)**
- ✅ P95 latency <100ms (verified)
- ✅ Response caching working
- ✅ Response compression enabled
- ✅ All I/O operations async

### **Errors (Task 2.4)**
- ✅ All error codes defined
- ✅ User-friendly messages implemented
- ✅ Retry logic working
- ✅ Error documentation complete

### **Security (Task 2.5)**
- ✅ Input validation comprehensive
- ✅ No SQL injection vulnerabilities
- ✅ PII sanitized in logs
- ✅ CORS properly configured
- ✅ Rate limiting verified
- ✅ Security audit complete

### **Documentation (Task 2.6)**
- ✅ OpenAPI schema complete
- ✅ All endpoints documented
- ✅ Examples provided
- ✅ Swagger UI working
- ✅ ReDoc working

---

## **📅 TIMELINE**

### **Day 1 (8 hours)**
- Morning: Task 2.1 - Integration tests (3h)
- Afternoon: Task 2.1 - Load & performance tests (2h)
- Evening: Task 2.1 - Security tests (2h)
- End of day: Task 2.1 - Edge case tests (1h)

### **Day 2 (8 hours)**
- Morning: Task 2.2 - Database indexes (2h)
- Late morning: Task 2.2 - Connection pooling (2h)
- Afternoon: Task 2.2 - Query optimization (2h)
- Evening: Task 2.3 - Response caching (2h)

### **Day 3 (8 hours)**
- Morning: Task 2.3 - Response compression & async I/O (2h)
- Late morning: Task 2.4 - Standardized errors (2h)
- Afternoon: Task 2.4 - User-friendly messages & retry (2h)
- Evening: Task 2.5 - Input validation (2h)

### **Day 4 (8 hours)**
- Morning: Task 2.5 - SQL injection & PII handling (2h)
- Late morning: Task 2.5 - CORS & rate limiting (2h)
- Afternoon: Task 2.6 - OpenAPI schema (2h)
- Evening: Task 2.6 - Endpoint documentation (2h)

### **Total: 32 hours over 4 days**

---

## **🚀 NEXT STEPS**

### **After Phase 2 Complete:**
1. ✅ Comprehensive test suite (200+ tests, 95%+ coverage)
2. ✅ Optimized database (<50ms queries)
3. ✅ Fast API (<100ms responses)
4. ✅ User-friendly errors
5. ✅ Production-grade security
6. ✅ Complete API documentation

### **Then Move to Phase 4:**
- Dashboard/Frontend (80 hours)
- Visual insights for customers
- Customer-facing features
- MVP Launch! 🎉

---

## **📝 NOTES**

### **Phase 2 vs Master Plan Differences**
The current Phase 2 (from HANDOVER_TO_PHASE_2.md) is slightly different from the original master plan:

**Original Master Plan Phase 2:**
- Task 2.1-2.2: CloudWatch metrics & alerts (already done in Task 1.3)
- Task 2.3: Data quality reporting
- Task 2.4: Database connection pool fix
- Task 2.5-2.6: Unit & integration tests

**Updated Phase 2 (Current):**
- Task 2.1: Comprehensive testing (combines 2.5-2.6)
- Task 2.2: Database optimization (expands 2.4)
- Task 2.3: API performance (new)
- Task 2.4: Error handling (new)
- Task 2.5: Security audit (new)
- Task 2.6: API documentation (new)

The updated version is MORE comprehensive and better prepares the system for production launch.

### **Dependencies**
- ✅ No external dependencies
- ✅ No waiting for AWS changes
- ✅ Can start immediately
- ✅ No coordination needed with frontend (yet)

### **Risks**
- ⚠️ Testing may uncover bugs that need fixing (add buffer time)
- ⚠️ Database migration downtime (minimal, <1 minute)
- ⚠️ Performance optimization may require iterative tuning

---

**Ready to start Phase 2!** 🚀

