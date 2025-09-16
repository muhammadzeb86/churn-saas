"""
S3 Service for handling file uploads and operations
"""
import boto3
import os
from datetime import datetime
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)

class S3Service:
    """Service class for S3 operations"""
    
    def __init__(self):
        """Initialize S3 client with configuration from environment"""
        self.s3_client = boto3.client(
            's3',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.bucket_name = os.getenv('S3_BUCKET')
        
        # Don't raise error if S3_BUCKET is not set - will use local fallback
        if not self.bucket_name:
            logger.warning("S3_BUCKET environment variable not set - will use local storage fallback")
            self.bucket_name = "local-storage"
    
    def upload_file_stream(self, file_content: bytes, user_id: str, filename: str) -> Dict[str, Any]:
        """
        Upload file content directly to S3 without saving to local disk
        
        Args:
            file_content: File content as bytes
            user_id: User ID for organizing uploads
            filename: Original filename
            
        Returns:
            Dict containing upload result with object_key and success status
        """
        try:
            # Generate S3 object key with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            object_key = f"uploads/{user_id}/{timestamp}-{filename}"
            
            # Upload file content directly to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_content,
                ContentType='text/csv'  # Assuming CSV files
            )
            
            logger.info(f"Successfully uploaded file to S3: {object_key}")
            
            return {
                "success": True,
                "object_key": object_key,
                "bucket": self.bucket_name,
                "filename": filename,
                "size": len(file_content)
            }
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return {
                "success": False,
                "error": "AWS credentials not configured"
            }
        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}")
            return {
                "success": False,
                "error": f"S3 upload failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {str(e)}")
            return {
                "success": False,
                "error": f"Upload failed: {str(e)}"
            }
    
    def generate_presigned_upload_url(self, user_id: str, filename: str, expiration: int = 3600) -> Dict[str, Any]:
        """
        Generate a presigned URL for direct client-side uploads
        
        Args:
            user_id: User ID for organizing uploads
            filename: Original filename
            expiration: URL expiration time in seconds (default 1 hour)
            
        Returns:
            Dict containing presigned URL and object key
        """
        try:
            # Generate S3 object key
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            object_key = f"uploads/{user_id}/{timestamp}-{filename}"
            
            # Generate presigned URL for PUT operation
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key,
                    'ContentType': 'text/csv'
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for: {object_key}")
            
            return {
                "success": True,
                "presigned_url": presigned_url,
                "object_key": object_key,
                "expires_in": expiration
            }
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return {
                "success": False,
                "error": "AWS credentials not configured"
            }
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to generate presigned URL: {str(e)}"
            }
    
    def get_file_url(self, object_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for downloading a file
        
        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned download URL or None if failed
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate download URL: {str(e)}")
            return None
    
    def generate_presigned_download_url(self, object_key: str, expires_in: int = 3600, 
                              http_method: str = 'GET', content_disposition: str = None) -> str:
        """
        Generate a presigned URL for file operations with advanced options
        
        Args:
            object_key: S3 object key
            expires_in: URL expiration time in seconds
            http_method: HTTP method ('GET', 'PUT', etc.)
            content_disposition: Content-Disposition header for downloads
            
        Returns:
            Presigned URL
            
        Raises:
            Exception: If URL generation fails
        """
        try:
            operation = 'get_object' if http_method.upper() == 'GET' else 'put_object'
            
            params = {
                'Bucket': self.bucket_name,
                'Key': object_key
            }
            
            # Add Content-Disposition if specified (for downloads)
            if content_disposition and http_method.upper() == 'GET':
                params['ResponseContentDisposition'] = content_disposition
            
            url = self.s3_client.generate_presigned_url(
                operation,
                Params=params,
                ExpiresIn=expires_in
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {object_key}: {str(e)}")
            raise
    
    def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            object_key: S3 object key
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"Successfully deleted file: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {object_key}: {str(e)}")
            return False
    
    def download_file(self, object_key: str, local_path: str) -> Dict[str, Any]:
        """
        Download a file from S3 to local path
        
        Args:
            object_key: S3 object key
            local_path: Local file path to save to
            
        Returns:
            Dict containing success status and error info
        """
        try:
            self.s3_client.download_file(self.bucket_name, object_key, local_path)
            logger.info(f"Successfully downloaded {object_key} to {local_path}")
            return {
                "success": True,
                "local_path": local_path,
                "object_key": object_key
            }
        except ClientError as e:
            error_msg = f"S3 download failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    def file_exists(self, object_key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            object_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
        except Exception:
            return False

# Global S3 service instance
s3_service = S3Service() 
