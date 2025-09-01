from datetime import datetime
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True  # Enables ORM mode for Pydantic

class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    upload_time: datetime
    user_id: str

    class Config:
        from_attributes = True 