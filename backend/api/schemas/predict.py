from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class PredictionResponse(BaseModel):
    """Schema for retention prediction response."""
    message: str
    prediction_file: str
    sample_predictions: List[Dict[str, Any]]
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "message": "Predictions completed successfully",
                "prediction_file": "C:/Projects/retainwise/backend/ml/predictions/1_predicted_20250526_223737.csv",
                "sample_predictions": [
                    {
                        "customerID": "7590-VHVEG",
                        "gender": "Female",
                        "SeniorCitizen": 0,
                        "Partner": "Yes",
                        "Dependents": "No",
                        "tenure": 1,
                        "PhoneService": "Yes",
                        "MonthlyCharges": 29.85,
                        "TotalCharges": 29.85,
                        "retention_probability": 0.85,
                        "retention_prediction": 1,
                        "feature_importance": "Contract_Month-to-month decreases retention by 0.234; tenure increases retention by 0.156; MonthlyCharges decreases retention by 0.089"
                    }
                ]
            }
        } 
