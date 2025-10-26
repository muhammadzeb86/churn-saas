"""
Predictions API routes for managing ML prediction results
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any
import logging

from backend.api.database import get_db
from backend.models import Prediction, PredictionStatus
from backend.services.s3_service import s3_service
from backend.core.config import settings
from backend.auth.middleware import get_current_user, require_user_ownership

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
    user_id: str = Query(..., description="User ID to filter predictions"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get latest 20 predictions for a user
    
    Args:
        user_id: ID of the user
        db: Database session
        
    Returns:
        List of predictions with basic information
    """
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Query latest 20 predictions for user
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
        
    except Exception as e:
        logger.error(f"Error retrieving predictions for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving predictions"
        )

@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction_detail(
    prediction_id: str,
    user_id: str = Query(..., description="User ID for ownership verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific prediction
    
    Args:
        prediction_id: UUID of the prediction
        user_id: ID of the user (for ownership verification)
        db: Database session
        
    Returns:
        Detailed prediction information
    """
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Query prediction by ID
        stmt = select(Prediction).where(Prediction.id == prediction_id)
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction with ID {prediction_id} not found"
            )
        
        # Check ownership
        if prediction.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't have permission to view this prediction"
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
        
        logger.info(f"Retrieved prediction details for {prediction_id}, user {user_id}")
        
        return PredictionDetailResponse(
            success=True,
            prediction=prediction_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving prediction {prediction_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving prediction details"
        )

@router.get("/download_predictions/{prediction_id}", response_model=DownloadUrlResponse)
async def download_prediction_results(
    prediction_id: str,
    user_id: str = Query(..., description="User ID for ownership verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a presigned download URL for prediction results
    
    Args:
        prediction_id: UUID of the prediction
        user_id: ID of the user (for ownership verification)
        db: Database session
        
    Returns:
        Presigned download URL
    """
    try:
        # Verify user has access to this data
        require_user_ownership(user_id, current_user)
        
        # Query prediction by ID
        stmt = select(Prediction).where(Prediction.id == prediction_id)
        result = await db.execute(stmt)
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction with ID {prediction_id} not found"
            )
        
        # Check ownership
        if prediction.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't have permission to download this prediction"
            )
        
        # Check if prediction is completed and has output
        if prediction.status != PredictionStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Prediction is not completed (status: {prediction.status.value})"
            )
        
        if not prediction.s3_output_key:
            raise HTTPException(
                status_code=404,
                detail="No output file available for this prediction"
            )
        
        # Generate presigned URL for download
        expires_in = 600  # 10 minutes
        
        try:
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
            logger.error(f"Failed to generate presigned URL for {prediction.s3_output_key}: {str(s3_error)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate download URL"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating download URL for prediction {prediction_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating download URL"
        ) 
