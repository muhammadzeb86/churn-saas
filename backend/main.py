from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from backend.api.database import get_db, init_db
from backend.models import User
from backend.schemas import UserCreate, UserResponse
from typing import List
from backend.api.routes import predict, powerbi, upload

app = FastAPI(title="RetainWise Analytics API")

# Include routers
app.include_router(predict.router, prefix="/predict", tags=["predict"])
app.include_router(powerbi.router, prefix="/powerbi", tags=["powerbi"])
app.include_router(upload.router, tags=["upload"])  # Upload routes are at /upload/*

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def root():
    return JSONResponse(content={"message": "RetainWise Analytics backend is running"})

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return JSONResponse(content={"status": "healthy", "message": "RetainWise Analytics backend is running"})

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
