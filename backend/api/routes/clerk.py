"""
Clerk webhook routes for handling user events
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
import hmac
import hashlib
import os
import logging
from typing import Optional

from api.database import get_db
from models import User
from schemas.clerk import ClerkWebhookPayload, WebhookResponse, UserCreate, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clerk", tags=["clerk"])

def verify_clerk_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify Clerk webhook signature using HMAC-SHA256
    
    Args:
        payload: Raw request body
        signature: Signature from svix-signature header
        secret: Webhook secret from environment
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Extract timestamp and signature from svix-signature header
        # Format: "t=timestamp,v1=signature"
        parts = signature.split(',')
        timestamp = None
        signature_value = None
        
        for part in parts:
            if part.startswith('t='):
                timestamp = part[2:]
            elif part.startswith('v1='):
                signature_value = part[3:]
        
        if not timestamp or not signature_value:
            logger.error("Invalid svix-signature header format")
            return False
        
        # Create expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            f"{timestamp}.{payload.decode('utf-8')}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(expected_signature, signature_value)
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {str(e)}")
        return False

def extract_user_data_from_clerk(clerk_data) -> UserCreate:
    """
    Extract user data from Clerk webhook payload
    
    Args:
        clerk_data: Clerk user data from webhook
        
    Returns:
        UserCreate object with extracted data
    """
    # Get primary email address
    primary_email = None
    for email_data in clerk_data.email_addresses:
        if email_data.get('id') == clerk_data.primary_email_address_id:
            primary_email = email_data.get('email_address')
            break
    
    if not primary_email:
        # Fallback to first email address
        primary_email = clerk_data.email_addresses[0].get('email_address') if clerk_data.email_addresses else None
    
    if not primary_email:
        raise ValueError("No email address found in Clerk user data")
    
    # Build full name from first and last name
    first_name = clerk_data.first_name or ""
    last_name = clerk_data.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "Unknown User"
    
    return UserCreate(
        email=primary_email,
        clerk_id=clerk_data.id,
        full_name=full_name,
        first_name=clerk_data.first_name,
        last_name=clerk_data.last_name,
        avatar_url=clerk_data.image_url
    )

@router.post("/webhook", response_model=WebhookResponse)
async def clerk_webhook(
    request: Request,
    svix_signature: Optional[str] = Header(None),
    svix_timestamp: Optional[str] = Header(None),
    svix_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Clerk webhook events for user creation and updates
    
    Args:
        request: FastAPI request object
        svix_signature: Signature from Clerk webhook
        svix_timestamp: Timestamp from Clerk webhook
        svix_id: Webhook ID from Clerk
        db: Database session
        
    Returns:
        WebhookResponse with success status
    """
    try:
        # Get webhook secret from environment
        webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.error("CLERK_WEBHOOK_SECRET not configured")
            return WebhookResponse(
                success=False,
                message="Webhook secret not configured"
            )
        
        # Read request body
        payload = await request.body()
        
        # Verify webhook signature
        if not svix_signature:
            logger.error("Missing svix-signature header")
            return WebhookResponse(
                success=False,
                message="Missing signature header"
            )
        
        if not verify_clerk_webhook_signature(payload, svix_signature, webhook_secret):
            logger.error("Invalid webhook signature")
            return WebhookResponse(
                success=False,
                message="Invalid signature"
            )
        
        # Parse webhook payload
        try:
            webhook_data = ClerkWebhookPayload.model_validate_json(payload)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {str(e)}")
            return WebhookResponse(
                success=False,
                message="Invalid payload format"
            )
        
        # Extract user data
        clerk_user_data = webhook_data.data.data
        event_type = webhook_data.data.type
        
        logger.info(f"Processing Clerk webhook: {event_type} for user {clerk_user_data.id}")
        
        # Handle different event types
        if event_type == "user.created":
            return await handle_user_created(clerk_user_data, db)
        elif event_type == "user.updated":
            return await handle_user_updated(clerk_user_data, db)
        else:
            logger.info(f"Ignoring webhook event type: {event_type}")
            return WebhookResponse(
                success=True,
                message=f"Event type {event_type} ignored"
            )
            
    except Exception as e:
        logger.error(f"Error processing Clerk webhook: {str(e)}")
        return WebhookResponse(
            success=False,
            message="Internal server error"
        )

async def handle_user_created(clerk_user_data, db: AsyncSession) -> WebhookResponse:
    """
    Handle user.created webhook event
    
    Args:
        clerk_user_data: Clerk user data
        db: Database session
        
    Returns:
        WebhookResponse
    """
    try:
        # Extract user data
        user_data = extract_user_data_from_clerk(clerk_user_data)
        
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.clerk_id == user_data.clerk_id)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info(f"User already exists: {user_data.clerk_id}")
            return WebhookResponse(
                success=True,
                message="User already exists"
            )
        
        # Create new user
        new_user = User(
            email=user_data.email,
            clerk_id=user_data.clerk_id,
            full_name=user_data.full_name,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            avatar_url=user_data.avatar_url
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"Created new user: {new_user.id} ({user_data.email})")
        
        return WebhookResponse(
            success=True,
            message="User created successfully"
        )
        
    except IntegrityError:
        await db.rollback()
        logger.warning(f"User creation failed due to integrity error: {clerk_user_data.id}")
        return WebhookResponse(
            success=True,
            message="User already exists"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating user: {str(e)}")
        return WebhookResponse(
            success=False,
            message="Failed to create user"
        )

async def handle_user_updated(clerk_user_data, db: AsyncSession) -> WebhookResponse:
    """
    Handle user.updated webhook event
    
    Args:
        clerk_user_data: Clerk user data
        db: Database session
        
    Returns:
        WebhookResponse
    """
    try:
        # Find existing user
        result = await db.execute(
            select(User).where(User.clerk_id == clerk_user_data.id)
        )
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            logger.warning(f"User not found for update: {clerk_user_data.id}")
            return WebhookResponse(
                success=False,
                message="User not found"
            )
        
        # Extract updated user data
        user_data = extract_user_data_from_clerk(clerk_user_data)
        
        # Update user fields
        existing_user.email = user_data.email
        existing_user.full_name = user_data.full_name
        existing_user.first_name = user_data.first_name
        existing_user.last_name = user_data.last_name
        existing_user.avatar_url = user_data.avatar_url
        
        await db.commit()
        await db.refresh(existing_user)
        
        logger.info(f"Updated user: {existing_user.id} ({user_data.email})")
        
        return WebhookResponse(
            success=True,
            message="User updated successfully"
        )
        
    except IntegrityError:
        await db.rollback()
        logger.error(f"User update failed due to integrity error: {clerk_user_data.id}")
        return WebhookResponse(
            success=False,
            message="Update failed due to constraint violation"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user: {str(e)}")
        return WebhookResponse(
            success=False,
            message="Failed to update user"
        ) 
