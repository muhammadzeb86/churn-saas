from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from backend.api.database import get_db, init_db
from backend.models import User, Upload
from backend.schemas import UserCreate, UserResponse, UploadResponse
from backend.utils import validate_csv_file, save_upload_file
from typing import List
from backend.api.routes import predict, powerbi

app = FastAPI(title="RetainWise Analytics API")

# Include routers
app.include_router(predict.router, prefix="/predict", tags=["predict"])
app.include_router(powerbi.router, prefix="/powerbi", tags=["powerbi"])

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def root():
    return JSONResponse(content={"message": "RetainWise Analytics backend is running"})

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

@app.post("/upload_csv", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Validate user exists
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Validate file
        validate_csv_file(file)
        
        # Save file
        file_path = await save_upload_file(file, user_id)
        
        # Create upload record
        upload = Upload(
            filename=file_path,
            user_id=user_id,
            status="pending"
        )
        
        # Save to database
        db.add(upload)
        await db.commit()
        await db.refresh(upload)
        
        return upload
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the upload: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
