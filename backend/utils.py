import os
from pathlib import Path
from fastapi import HTTPException, UploadFile
from datetime import datetime

# Maximum file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

def validate_csv_file(file: UploadFile) -> None:
    """Validate that the file is a CSV and under size limit."""
    # Check file extension
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )
    
    # Check file size
    try:
        file_size = 0
        while chunk := file.file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB"
                )
        # Reset file pointer to beginning
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error validating file: {str(e)}"
        )

async def save_upload_file(file: UploadFile, user_id: str) -> str:
    """Save the uploaded file to the uploads directory."""
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Create user-specific directory
    user_dir = uploads_dir / str(user_id)
    user_dir.mkdir(exist_ok=True)
    
    # Generate unique filename
    timestamp = Path(file.filename).stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.csv"
    file_path = user_dir / filename
    
    try:
        # Save the file
        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
        return str(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error saving file: {str(e)}"
        ) 
