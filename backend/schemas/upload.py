"""
Pydantic schemas for upload operations
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UploadResponse(BaseModel):
    """Response schema for file upload operations"""
    success: bool
    message: str
    upload_id: Optional[int] = None
    object_key: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None

class PresignedUrlResponse(BaseModel):
    """Response schema for presigned URL generation"""
    success: bool
    presigned_url: str
    object_key: str
    expires_in: int

class UploadInfo(BaseModel):
    """Schema for upload information"""
    id: int
    filename: str
    object_key: str
    file_size: Optional[int]
    upload_time: datetime
    status: str
    download_url: Optional[str] = None

class UserUploadsResponse(BaseModel):
    """Response schema for user uploads list"""
    success: bool
    uploads: list[UploadInfo]
    count: int 
