from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from backend.api.database import get_db, init_db
from backend.models import User
from backend.user_schemas import UserCreate, UserResponse
from typing import List
from backend.api.routes import predict, powerbi, upload, waitlist, clerk
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RetainWise Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://retainwiseanalytics.com",
        "https://www.retainwiseanalytics.com",
        "https://app.retainwiseanalytics.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(predict.router, prefix="/predict", tags=["predict"])
app.include_router(powerbi.router, prefix="/powerbi", tags=["powerbi"])
app.include_router(upload.router, tags=["upload"])  # Upload routes are at /upload/*
app.include_router(waitlist.router)  # Waitlist routes are at /api/waitlist/*
app.include_router(clerk.router)  # Clerk webhook routes are at /api/clerk/*

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup - handle failures gracefully"""
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        print("Application will continue running, but database operations may fail")

@app.get("/")
async def root():
    return JSONResponse(content={"message": "RetainWise Analytics backend is running"})

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer - basic app health only"""
    return {"status": "healthy", "service": "retainwise-backend"}

@app.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check including database connectivity"""
    try:
        # Test the database connection
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        return {
            "status": "healthy", 
            "service": "retainwise-backend",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy",
                "service": "retainwise-backend", 
                "database": "disconnected",
                "error": str(e)
            }
        )

@app.get("/db-test")
async def test_db(db: AsyncSession = Depends(get_db)):
    try:
        # Test the database connection using SQLAlchemy
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        return {"message": "Successfully connected to the database"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.post("/users", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Create new user instance
        user = User(
            email=user_data.email,
            full_name=user_data.full_name
        )
        
        # Add to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while creating the user: {str(e)}"
        )

@app.get("/users", response_model=List[UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    try:
        # Query all users
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()
        return users
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching users: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
