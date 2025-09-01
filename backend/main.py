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
from api.health import db_ping_ok

app = FastAPI(title="RetainWise Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://retainwiseanalytics.com",
        "https://www.retainwiseanalytics.com",
        "https://app.retainwiseanalytics.com",
        "https://backend.retainwiseanalytics.com"
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
async def detailed_health_check():
    """Detailed health check including database connectivity"""
    try:
        # Test the database connection using the helper
        db_ok = await db_ping_ok()
        if not db_ok:
            raise Exception("Database ping failed")
        
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
        result.fetchone()
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

@app.post("/auth/sync_user")
async def sync_user(user_data: dict, db: AsyncSession = Depends(get_db)):
    """
    Sync user data from frontend (Clerk user)
    
    Args:
        user_data: User data from Clerk
        db: Database session
        
    Returns:
        User sync response
    """
    try:
        # Extract user data
        clerk_id = user_data.get('id')
        email = user_data.get('email_addresses', [{}])[0].get('email_address') if user_data.get('email_addresses') else None
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip() or "Unknown User"
        avatar_url = user_data.get('image_url')
        
        if not clerk_id or not email:
            raise HTTPException(
                status_code=400,
                detail="Missing required user data (id or email)"
            )
        
        # Check if user already exists
        result = await db.execute(select(User).where(User.clerk_id == clerk_id))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update existing user
            existing_user.email = email
            existing_user.full_name = full_name
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.avatar_url = avatar_url
            
            await db.commit()
            await db.refresh(existing_user)
            
            return {
                "success": True,
                "message": "User updated successfully",
                "user": {
                    "id": existing_user.id,
                    "email": existing_user.email,
                    "full_name": existing_user.full_name
                }
            }
        else:
            # Create new user
            new_user = User(
                id=clerk_id,  # Use clerk_id as the primary key
                email=email,
                clerk_id=clerk_id,
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            return {
                "success": True,
                "message": "User created successfully",
                "user": {
                    "id": new_user.id,
                    "email": new_user.email,
                    "full_name": new_user.full_name
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while syncing user: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
