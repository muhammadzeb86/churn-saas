"""
Waitlist routes for handling email submissions
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
import re

from backend.api.database import get_db
from backend.models import WaitlistEmail
from backend.schemas import WaitlistRequest, WaitlistResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

def validate_email(email: str) -> bool:
    """Simple email validation using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@router.post("", response_model=WaitlistResponse)
async def join_waitlist(
    request: WaitlistRequest,
    db: Session = Depends(get_db)
):
    """
    Add email to waitlist
    
    Args:
        request: WaitlistRequest containing email
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
        existing_email = db.query(WaitlistEmail).filter(
            WaitlistEmail.email == request.email
        ).first()
        
        if existing_email:
            # Return success for duplicate emails (idempotent)
            return WaitlistResponse(
                success=True,
                message="Email already registered for waitlist"
            )
        
        # Create new waitlist entry
        waitlist_entry = WaitlistEmail(email=request.email)
        db.add(waitlist_entry)
        db.commit()
        db.refresh(waitlist_entry)
        
        logger.info(f"New waitlist signup: {request.email}")
        
        return WaitlistResponse(
            success=True,
            message="Successfully added to waitlist"
        )
        
    except IntegrityError:
        # Handle race condition where email was added between check and insert
        db.rollback()
        return WaitlistResponse(
            success=True,
            message="Email already registered for waitlist"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding email to waitlist: {str(e)}")
        return WaitlistResponse(
            success=False,
            error="Internal server error"
        ) 