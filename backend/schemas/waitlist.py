"""
Pydantic schemas for waitlist operations
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class WaitlistRequest(BaseModel):
    """Request schema for waitlist email submission"""
    email: EmailStr
    source: Optional[str] = "landing_page"

class WaitlistResponse(BaseModel):
    """Response schema for waitlist operations"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class LeadInfo(BaseModel):
    """Schema for lead information"""
    id: int
    email: str
    joined_at: datetime
    source: Optional[str] = None
    converted_to_user: bool

    class Config:
        from_attributes = True 
