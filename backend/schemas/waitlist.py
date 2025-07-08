"""
Pydantic schemas for waitlist operations
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class WaitlistRequest(BaseModel):
    """Request schema for waitlist email submission"""
    email: EmailStr

class WaitlistResponse(BaseModel):
    """Response schema for waitlist operations"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class WaitlistEmailInfo(BaseModel):
    """Schema for waitlist email information"""
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True 