"""
Waitlist routes for handling email submissions
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
import logging
import re

from backend.api.database import get_db
from backend.models import Lead
from backend.schemas.waitlist import WaitlistRequest, WaitlistResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

def validate_email(email: str) -> bool:
    """Simple email validation using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@router.post("", response_model=WaitlistResponse)
async def join_waitlist(
    request: WaitlistRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Add email to waitlist
    
    Args:
        request: WaitlistRequest containing email and source
        db: Database session
        
    Returns:
        WaitlistResponse with success status
    """
    try:
        # Validate email format
        if not validate_email(request.email):
            return WaitlistResponse(
                success=False,
                error="Invalid email format"
            )
        
        # Check if email already exists
        result = await db.execute(
            select(Lead).where(Lead.email == request.email)
        )
        existing_lead = result.scalar_one_or_none()
        
        if existing_lead:
            # Return success for duplicate emails (idempotent)
            return WaitlistResponse(
                success=True,
                message="Email already registered for waitlist"
            )
        
        # Create new lead entry
        lead_entry = Lead(
            email=request.email,
            source=request.source
        )
        db.add(lead_entry)
        await db.commit()
        await db.refresh(lead_entry)
        
        logger.info(f"New waitlist signup: {request.email} from {request.source}")
        
        return WaitlistResponse(
            success=True,
            message="Successfully added to waitlist"
        )
        
    except IntegrityError:
        # Handle race condition where email was added between check and insert
        await db.rollback()
        return WaitlistResponse(
            success=True,
            message="Email already registered for waitlist"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error adding email to waitlist: {str(e)}")
        return WaitlistResponse(
            success=False,
            error="Internal server error"
        ) 
