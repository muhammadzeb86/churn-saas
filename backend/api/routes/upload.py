"""
Upload routes for handling CSV file uploads to S3
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import logging

from backend.api.database import get_db
from backend.models import Upload, User
from backend.services.s3_service import s3_service
from backend.schemas import UploadResponse, PresignedUrlResponse, UploadInfo, UserUploadsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("/csv", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
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
    try:
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
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Upload file to S3
        upload_result = s3_service.upload_file_stream(
            file_content=file_content,
            user_id=str(user_id),
            filename=file.filename
        )
        
        if not upload_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Upload failed: {upload_result.get('error', 'Unknown error')}"
            )
        
        # Store upload record in database
        upload_record = Upload(
            filename=file.filename,
            s3_object_key=upload_result["object_key"],
            file_size=upload_result["size"],
            user_id=user_id,
            status="uploaded"
        )
        
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        
        logger.info(f"Successfully uploaded CSV file: {file.filename} for user {user_id}")
        
        return UploadResponse(
            success=True,
            message="File uploaded successfully",
            upload_id=upload_record.id,
            object_key=upload_result["object_key"],
            filename=file.filename,
            file_size=upload_result["size"]
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
    user_id: int = Form(...),
    db: Session = Depends(get_db)
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
        presigned_result = s3_service.generate_presigned_url(
            user_id=str(user_id),
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
    user_id: int = Form(...),
    filename: str = Form(...),
    file_size: Optional[int] = Form(None),
    db: Session = Depends(get_db)
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
    user_id: int,
    db: Session = Depends(get_db)
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