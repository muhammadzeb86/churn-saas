"""
SQS Message Schemas
===================
Pydantic validation schemas for SQS messages.

Security Features:
- UUID validation (prevents injection)
- S3 path validation (prevents path traversal)
- User ID format validation (Clerk pattern)
- Timestamp validation (prevents old messages)
"""

from pydantic import BaseModel, Field, UUID4, validator
from datetime import datetime
from typing import Literal
import re

class PredictionSQSMessage(BaseModel):
    """
    Schema for prediction job messages in SQS
    
    Example:
        {
            "prediction_id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "user_2abcdef1234567890",
            "upload_id": "15",
            "s3_file_path": "s3://retainwise-uploads/user_abc/file.csv",
            "timestamp": "2025-11-02T12:34:56.789Z",
            "priority": "normal"
        }
    """
    
    prediction_id: UUID4 = Field(
        ...,
        description="UUID of the prediction record in database"
    )
    
    user_id: str = Field(
        ...,
        min_length=5,
        max_length=50,
        description="Clerk user ID (format: user_xxxx)"
    )
    
    upload_id: str = Field(
        ...,
        description="ID of the upload record in database (integer as string)"
    )
    
    s3_file_path: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="S3 path to uploaded CSV file"
    )
    
    timestamp: datetime = Field(
        ...,
        description="When message was published (ISO 8601)"
    )
    
    priority: Literal['normal', 'high'] = Field(
        default='normal',
        description="Processing priority (normal for Phase 1)"
    )
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """
        Validate Clerk user ID format
        
        Valid: user_2abcdef1234567890
        Invalid: user_<script>alert('xss')</script>
        """
        if not re.match(r'^user_[a-zA-Z0-9_]{20,40}$', v):
            raise ValueError(f'Invalid Clerk user ID format: {v}')
        return v
    
    @validator('s3_file_path')
    def validate_s3_path(cls, v):
        """
        Validate S3 path format and prevent attacks
        
        Valid: s3://retainwise-uploads/user_abc/file.csv
        Invalid: s3://other-bucket/file.csv (wrong bucket)
        Invalid: s3://retainwise-uploads/../../../etc/passwd (path traversal)
        Invalid: s3://retainwise-uploads/file.sh (wrong extension)
        """
        # Must start with our bucket prefix
        if not v.startswith('s3://retainwise-'):
            raise ValueError(f'S3 path must be in retainwise-* bucket: {v}')
        
        # No path traversal attempts
        if '../' in v:
            raise ValueError(f'Path traversal detected in S3 path: {v}')
        
        # No double slashes (except s3://)
        if '//' in v.replace('s3://', '', 1):
            raise ValueError(f'Invalid S3 path format: {v}')
        
        # Must end with .csv
        if not v.lower().endswith('.csv'):
            raise ValueError(f'S3 path must point to CSV file: {v}')
        
        # No special characters that could cause issues
        if any(char in v for char in ['<', '>', '|', '&', ';', '`', '$', '(', ')', '{', '}']):
            raise ValueError(f'Invalid characters in S3 path: {v}')
        
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        """
        Ensure timestamp is recent
        
        Prevents replay attacks with old messages
        Max age: 24 hours
        """
        age = datetime.utcnow() - v.replace(tzinfo=None)
        if age.total_seconds() > 86400:  # 24 hours
            raise ValueError(f'Message timestamp too old: {v} (age: {age})')
        
        # Also prevent future timestamps (clock skew attack)
        if age.total_seconds() < -3600:  # 1 hour in future
            raise ValueError(f'Message timestamp in future: {v}')
        
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z',
            UUID4: str
        }
        schema_extra = {
            "example": {
                "prediction_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user_2abcdef1234567890abcdef",
                "upload_id": "123",  # Integer ID as string
                "s3_file_path": "s3://retainwise-uploads/user_abc123/sample.csv",
                "timestamp": "2025-11-02T12:34:56.789Z",
                "priority": "normal"
            }
        }

