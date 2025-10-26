"""
Upload routes for handling CSV file uploads to S3
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
import logging

from backend.api.database import get_db
from backend.models import Upload, User, Prediction, PredictionStatus
from backend.services.s3_service import s3_service
from backend.services.sqs_service import publish_prediction_task
from backend.schemas.upload import UploadResponse, PresignedUrlResponse, UploadInfo, UserUploadsResponse
from backend.core.config import settings
from backend.auth.middleware import get_current_user, require_user_ownership

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

@router.post("/csv", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a CSV file directly to S3 and store metadata in database
    
    Args:
        file: CSV file to upload
        user_id: ID of the user uploading the file
        db: Database session
        
    Returns:
        Upload response with success status and object key
    """
    logger.info(f"Received upload request for user_id: {user_id}, filename: {file.filename}")
    try:
        # Verify user has access to upload for this user_id
        require_user_ownership(user_id, current_user)
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=400, 
                detail="Only CSV files are allowed"
            )
        
        # Validate file size (e.g., max 10MB)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )
        
        # Check if user exists
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Try to upload file to S3, fallback to local storage if AWS credentials not available
        try:
            upload_result = s3_service.upload_file_stream(
                file_content=file_content,
                user_id=user_id,  # Already a string now
                filename=file.filename
            )
            
            if not upload_result["success"]:
                # Fallback to local storage
                import os
                from pathlib import Path
                
                # Create uploads directory
                uploads_dir = Path("uploads") / user_id  # Already a string now
                uploads_dir.mkdir(parents=True, exist_ok=True)
                
                # Save file locally
                file_path = uploads_dir / f"{file.filename}"
                with open(file_path, "wb") as f:
                    f.write(file_content)
                
                upload_result = {
                    "success": True,
                    "object_key": f"local/{user_id}/{file.filename}",
                    "size": len(file_content)
                }
                
                logger.info(f"Saved file locally: {file_path}")
        except Exception as s3_error:
            logger.warning(f"S3 upload failed, using local storage: {s3_error}")
            
            # Fallback to local storage
            import os
            from pathlib import Path
            
            # Create uploads directory
            uploads_dir = Path("uploads") / user_id  # Already a string now
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file locally
            file_path = uploads_dir / f"{file.filename}"
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            upload_result = {
                "success": True,
                "object_key": f"local/{user_id}/{file.filename}",
                "size": len(file_content)
            }
            
            logger.info(f"Saved file locally: {file_path}")
        
        # Begin transaction - create Upload and Prediction records
        try:
            # Create upload record
            upload_record = Upload(
                filename=file.filename,
                s3_object_key=upload_result["object_key"],
                file_size=upload_result["size"],
                user_id=user_id,
                status="uploaded"
            )
            db.add(upload_record)
            
            # Flush to get upload_id
            await db.flush()
            
            # Create prediction record
            prediction_record = Prediction(
                upload_id=upload_record.id,
                user_id=user_id,
                status=PredictionStatus.QUEUED
            )
            db.add(prediction_record)
            
            # Flush to get prediction_id
            await db.flush()
            
            # Commit transaction
            await db.commit()
            await db.refresh(upload_record)
            await db.refresh(prediction_record)
            
            logger.info(f"upload: created prediction - upload_id={upload_record.id}, prediction_id={prediction_record.id}, user_id={user_id}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Database transaction failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create upload and prediction records")
        
        # After successful commit, publish to SQS (if available)
        publish_warning = False
        prediction_status = "QUEUED"
        
        if settings.PREDICTIONS_QUEUE_URL:
            try:
                await publish_prediction_task(
                    queue_url=settings.PREDICTIONS_QUEUE_URL,
                    prediction_id=str(prediction_record.id),
                    upload_id=str(upload_record.id),
                    user_id=user_id,
                    s3_key=upload_result["object_key"]
                )
                logger.info(f"upload: published sqs message - prediction_id={prediction_record.id}, message_body={{upload_id: {upload_record.id}, s3_key: {upload_result['object_key']}}}")
                
            except Exception as e:
                # SQS publish failed - update prediction status
                logger.error(f"upload: publish failed - prediction_id={prediction_record.id}, error={str(e)}")
                
                try:
                    # Start new transaction to update prediction status
                    prediction_record.status = PredictionStatus.FAILED
                    prediction_record.error_message = f"SQS publish failed: {str(e)}"
                    db.add(prediction_record)
                    await db.commit()
                    
                    publish_warning = True
                    prediction_status = "FAILED"
                    
                except Exception as db_error:
                    logger.error(f"Failed to update prediction status after SQS failure: {str(db_error)}")
        else:
            logger.info(f"upload: SQS disabled - prediction {prediction_record.id} created but not queued for processing")
        
        logger.info(f"Successfully uploaded CSV file: {file.filename} for user {user_id}")
        
        return UploadResponse(
            success=True,
            message="File uploaded successfully",
            upload_id=upload_record.id,
            object_key=upload_result["object_key"],
            filename=file.filename,
            file_size=upload_result["size"],
            prediction_id=str(prediction_record.id),
            prediction_status=prediction_status,
            publish_warning=publish_warning if publish_warning else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during upload"
        )

@router.post("/presign", response_model=PresignedUrlResponse)
async def get_presigned_upload_url(
    filename: str = Form(...),
    user_id: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a presigned URL for client-side direct upload to S3
    
    Args:
        filename: Name of the file to upload
        user_id: ID of the user uploading the file
        db: Database session
        
    Returns:
        Presigned URL response for direct upload
    """
    try:
        # Verify user has access to upload for this user_id
        require_user_ownership(user_id, current_user)
        
        # Validate filename
        if not filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Only CSV files are allowed"
            )
        
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Generate presigned URL
        presigned_result = s3_service.generate_presigned_upload_url(
            user_id=user_id,
            filename=filename
        )
        
        if not presigned_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate presigned URL: {presigned_result.get('error', 'Unknown error')}"
            )
        
        logger.info(f"Generated presigned URL for user {user_id}, file: {filename}")
        
        return PresignedUrlResponse(
            success=True,
            presigned_url=presigned_result["presigned_url"],
            object_key=presigned_result["object_key"],
            expires_in=presigned_result["expires_in"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error generating presigned URL"
        )

@router.post("/confirm-upload")
async def confirm_upload(
    object_key: str = Form(...),
    user_id: str = Form(...),
    filename: str = Form(...),
    file_size: Optional[int] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm a client-side upload by storing metadata in database
    
    This endpoint is called after a successful client-side upload to S3
    to record the upload in the database.
    
    Args:
        object_key: S3 object key of the uploaded file
        user_id: ID of the user who uploaded the file
        filename: Original filename
        file_size: Size of the file in bytes (optional)
        db: Database session
        
    Returns:
        Confirmation response
    """
    try:
        # Verify user has access to confirm upload for this user_id
        require_user_ownership(user_id, current_user)
        
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Verify file exists in S3
        if not s3_service.file_exists(object_key):
            raise HTTPException(
                status_code=404,
                detail="Uploaded file not found in S3"
            )
        
        # Store upload record in database
        upload_record = Upload(
            filename=filename,
            s3_object_key=object_key,
            file_size=file_size,
            user_id=user_id,
            status="uploaded"
        )
        
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        
        logger.info(f"Confirmed upload: {filename} for user {user_id}")
        
        return {
            "success": True,
            "message": "Upload confirmed and recorded",
            "upload_id": upload_record.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error confirming upload"
        )

@router.get("/files/{user_id}")
async def get_user_uploads(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all uploads for a specific user
    
    Args:
        user_id: ID of the user
        db: Database session
        
    Returns:
        List of user's uploads
    """
    try:
        # Verify user has access to view uploads for this user_id
        require_user_ownership(user_id, current_user)
        
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Get user's uploads
        uploads = db.query(Upload).filter(Upload.user_id == user_id).all()
        
        upload_list = []
        for upload in uploads:
            # Generate download URL for each file
            download_url = s3_service.get_file_url(upload.s3_object_key)
            
            upload_list.append({
                "id": upload.id,
                "filename": upload.filename,
                "object_key": upload.s3_object_key,
                "file_size": upload.file_size,
                "upload_time": upload.upload_time,
                "status": upload.status,
                "download_url": download_url
            })
        
        return {
            "success": True,
            "uploads": upload_list,
            "count": len(upload_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user uploads: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving uploads"
        )

@router.get("/uploads")
async def get_uploads(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all uploads (for frontend compatibility)
    This endpoint returns an empty list since we need user context
    
    Args:
        db: Database session
        
    Returns:
        Empty uploads list
    """
    try:
        # For now, return empty list since we don't have user context
        # In a real app, you'd get the user from JWT token or session
        return {
            "success": True,
            "uploads": [],
            "count": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting uploads: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving uploads"
        ) 
