from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import pandas as pd
from pathlib import Path

from backend.api.database import get_db
from backend.models import Upload
from backend.api.schemas.predict import PredictionResponse
from backend.ml.predict import RetentionPredictor

router = APIRouter()

# Initialize the predictor
predictor = RetentionPredictor()

@router.post("/predict_retention", response_model=PredictionResponse)
async def predict_retention(upload_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Make retention predictions on uploaded data.
    
    Args:
        upload_id: ID of the uploaded file in the database
        db: Database session
    
    Returns:
        Dictionary containing:
        - success message
        - prediction file path
        - sample predictions
    """
    try:
        # Get upload record from database
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            raise HTTPException(status_code=404, detail=f"Upload ID {upload_id} not found")
        
        # Check if file exists
        file_path = Path(upload.filename)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Load and validate data
        try:
            df = pd.read_csv(file_path)
            required_cols = [
                'customerID', 'gender', 'SeniorCitizen', 'Partner', 'Dependents',
                'tenure', 'PhoneService', 'MultipleLines', 'InternetService',
                'OnlineSecurity', 'OnlineBackup', 'DeviceProtection', 'TechSupport',
                'StreamingTV', 'StreamingMovies', 'Contract', 'PaperlessBilling',
                'PaymentMethod', 'MonthlyCharges', 'TotalCharges'
            ]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required columns: {', '.join(missing_cols)}"
                )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        
        # Make predictions
        df_predicted = predictor.predict(df)
        
        # Save predictions
        output_path = predictor.save_predictions(df_predicted, upload_id)
        
        # Update upload status
        upload.status = "processed"
        db.commit()
        
        # Get sample predictions
        sample_predictions = df_predicted.head().to_dict(orient='records')
        
        return {
            "message": "Predictions completed successfully",
            "prediction_file": str(output_path),
            "sample_predictions": sample_predictions
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download_predictions/{upload_id}")
async def download_predictions(upload_id: int, db: Session = Depends(get_db)):
    """
    Download predictions for a specific upload.
    
    Args:
        upload_id: ID of the uploaded file in the database
        db: Database session
    
    Returns:
        FileResponse containing the predictions CSV file
    """
    try:
        # Get upload record from database
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            raise HTTPException(status_code=404, detail=f"Upload ID {upload_id} not found")
            
        # Check if predictions exist
        predictions_path = Path("backend/ml/predictions") / f"predictions_{upload_id}.csv"
        if not predictions_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Predictions file not found. Please run predictions first."
            )
            
        return FileResponse(
            path=str(predictions_path),
            filename=f"churn_predictions_{upload_id}.csv",
            media_type="text/csv"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
