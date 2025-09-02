"""
Pydantic schemas for Clerk webhook events
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class ClerkUserData(BaseModel):
    """Clerk user data from webhook payload"""
    id: str = Field(..., description="Clerk user ID")
    email_addresses: list[Dict[str, Any]] = Field(..., description="User email addresses")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    created_at: int = Field(..., description="Unix timestamp")
    updated_at: int = Field(..., description="Unix timestamp")

class ClerkWebhookEvent(BaseModel):
    """Clerk webhook event structure"""
    data: ClerkUserData
    object: str = Field(..., description="Event object type")
    type: str = Field(..., description="Event type (e.g., user.created, user.updated)")

class ClerkWebhookPayload(BaseModel):
    """Complete Clerk webhook payload"""
    data: ClerkWebhookEvent
    object: str = Field(..., description="Webhook object type")
    type: str = Field(..., description="Webhook type")

class UserCreate(BaseModel):
    """Schema for creating a user from Clerk data"""
    email: str
    clerk_id: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    """Schema for updating a user from Clerk data"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None

class WebhookResponse(BaseModel):
    """Response schema for webhook endpoints"""
    success: bool
    message: str 
