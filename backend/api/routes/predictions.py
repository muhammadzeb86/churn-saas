"""
Predictions API routes for managing ML prediction results
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import List, Optional, Dict, Any
import logging
import uuid as uuid_lib

from backend.api.database import get_db
from backend.models import Prediction, PredictionStatus
from backend.services.s3_service import s3_service
from backend.core.config import settings
from backend.auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predictions"])

# Pydantic response models
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any

class PredictionListItem(BaseModel):
    """Schema for prediction list items"""
    id: str
    upload_id: int
    status: str
    rows_processed: int
    created_at: datetime
    has_output: bool

class PredictionDetail(BaseModel):
    """Schema for detailed prediction information"""
    id: str
    upload_id: int
    user_id: str
    status: str
    s3_output_key: Optional[str]
    rows_processed: int
    metrics_json: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

class PredictionListResponse(BaseModel):
    """Response schema for predictions list"""
    success: bool
    predictions: List[PredictionListItem]
    count: int

class PredictionDetailResponse(BaseModel):
    """Response schema for prediction details"""
    success: bool
    prediction: PredictionDetail

class DownloadUrlResponse(BaseModel):
    """Response schema for download URL"""
    success: bool
    download_url: str
    expires_in: int

@router.get("/", response_model=PredictionListResponse)
async def list_predictions(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get latest 20 predictions for the authenticated user
    
    Returns:
        List of predictions with basic information
    """
    try:
        # Extract user_id from JWT token (already validated by get_current_user)
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in authentication token"
            )
        
        # Query latest 20 predictions for authenticated user
        stmt = (
            select(Prediction)
            .where(Prediction.user_id == user_id)
            .order_by(desc(Prediction.created_at))
            .limit(20)
        )
        
        result = await db.execute(stmt)
        predictions = result.scalars().all()
        
        # Convert to response format
        prediction_items = []
        for pred in predictions:
            prediction_items.append(PredictionListItem(
                id=str(pred.id),
                upload_id=pred.upload_id,
                status=pred.status.value,
                rows_processed=pred.rows_processed,
                created_at=pred.created_at,
                has_output=bool(pred.s3_output_key and pred.status == PredictionStatus.COMPLETED)
            ))
        
        logger.info(f"Retrieved {len(prediction_items)} predictions for user {user_id}")
        
        return PredictionListResponse(
            success=True,
            predictions=prediction_items,
            count=len(prediction_items)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Secure error logging - don't leak sensitive details
        logger.error(f"Error retrieving predictions: {type(e).__name__} for user {current_user.get('id', 'unknown')}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve predictions"
        )

@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction_detail(
    prediction_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific prediction
    
    Security: User can only access their own predictions (enforced via JWT)
    
    Args:
        prediction_id: UUID of the prediction
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Detailed prediction information
        
    Raises:
        400: Invalid UUID format
        404: Prediction not found (or user doesn't own it - don't leak existence)
    """
    try:
        # Extract user_id from JWT token
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in authentication token"
            )
        
        # Validate and convert prediction_id to UUID
        try:
            prediction_uuid = uuid_lib.UUID(prediction_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid UUID format attempted: {prediction_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prediction ID format. Expected UUID, got: {prediction_id}"
            )
        
        # SECURITY: Query with ownership check - don't reveal existence if unauthorized
        stmt = select(Prediction).where(
            and_(
                Prediction.id == prediction_uuid,
                Prediction.user_id == user_id  # Enforce ownership in query
            )
        )
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            # Don't distinguish between "not found" and "not authorized"
            # This prevents leaking information about prediction existence
            raise HTTPException(
                status_code=404,
                detail="Prediction not found"
            )
        
        # Convert to response format
        prediction_detail = PredictionDetail(
            id=str(prediction.id),
            upload_id=prediction.upload_id,
            user_id=prediction.user_id,
            status=prediction.status.value,
            s3_output_key=prediction.s3_output_key,
            rows_processed=prediction.rows_processed,
            metrics_json=prediction.metrics_json,
            error_message=prediction.error_message,
            created_at=prediction.created_at,
            updated_at=prediction.updated_at
        )
        
        logger.info(f"Retrieved prediction details: {prediction_id} for user {user_id}")
        
        return PredictionDetailResponse(
            success=True,
            prediction=prediction_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Secure error logging - don't leak sensitive details
        user_id = current_user.get("id", "unknown")
        logger.error(f"Error retrieving prediction: {type(e).__name__} for user {user_id}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve prediction details"
        )

@router.get("/download_predictions/{prediction_id}", response_model=DownloadUrlResponse)
async def download_prediction_results(
    prediction_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a presigned download URL for prediction results
    
    Security: User can only download their own predictions
    
    Args:
        prediction_id: UUID of the prediction
        current_user: Authenticated user from JWT token
        db: Database session
        
    Returns:
        Presigned S3 download URL (valid for 10 minutes)
        
    Raises:
        400: Invalid UUID format or prediction not completed
        404: Prediction not found (or user doesn't own it)
    """
    try:
        # Extract user_id from JWT token
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in authentication token"
            )
        
        # Validate and convert prediction_id to UUID
        try:
            prediction_uuid = uuid_lib.UUID(prediction_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid UUID format attempted for download: {prediction_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prediction ID format. Expected UUID, got: {prediction_id}"
            )
        
        # SECURITY: Query with ownership check
        stmt = select(Prediction).where(
            and_(
                Prediction.id == prediction_uuid,
                Prediction.user_id == user_id  # Enforce ownership
            )
        )
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            # Don't distinguish between "not found" and "not authorized"
            raise HTTPException(
                status_code=404,
                detail="Prediction not found"
            )
        
        # Validate prediction is completed
        if prediction.status != PredictionStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Prediction is not completed yet (status: {prediction.status.value})"
            )
        
        if not prediction.s3_output_key:
            raise HTTPException(
                status_code=404,
                detail="No output file available for this prediction"
            )
        
        # Generate presigned URL for download (10 minutes expiry)
        expires_in = 600
        
        try:
            # Note: This is a LOCAL operation (cryptographic signing)
            # NO network I/O - just signs URL with AWS credentials
            # Therefore, NO need for asyncio.to_thread() wrapper
            presigned_url = s3_service.generate_presigned_download_url(
                object_key=prediction.s3_output_key,
                expires_in=expires_in,
                http_method='GET',
                content_disposition=f'attachment; filename="prediction_results_{prediction_id}.csv"'
            )
            
            logger.info(f"Generated download URL for prediction {prediction_id}, user {user_id}")
            
            return DownloadUrlResponse(
                success=True,
                download_url=presigned_url,
                expires_in=expires_in
            )
            
        except Exception as s3_error:
            logger.error(f"Failed to generate presigned URL: {type(s3_error).__name__} for prediction {prediction_id}")
            raise HTTPException(
                status_code=500,
                detail="Unable to generate download URL"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        # Secure error logging
        user_id = current_user.get("id", "unknown")
        logger.error(f"Error generating download URL: {type(e).__name__} for user {user_id}")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate download URL"
        ) 
