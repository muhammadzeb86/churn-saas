import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime
import warnings
from sklearn.preprocessing import StandardScaler
import logging
import xgboost as xgb
from sklearn.linear_model import LogisticRegression

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetentionPredictor:
    def __init__(self):
        """Initialize the predictor with paths and model."""
        self.base_path = Path(__file__).parent
        self.model_dir = self.base_path / 'models'
        self.predictions_dir = self.base_path / 'predictions'
        self.predictions_dir.mkdir(exist_ok=True)
        
        # Load the latest model
        self.model = self._load_latest_model()
        
        # Initialize scaler
        self.scaler = StandardScaler()
    
    def _load_latest_model(self):
        """Load the most recent model from the models directory."""
        try:
            model_files = list(self.model_dir.glob('best_retention_model_*.pkl'))
            if not model_files:
                raise FileNotFoundError("No model files found in models directory")
            
            latest_model = max(model_files, key=lambda x: x.stat().st_mtime)
            logger.info(f"Loading model: {latest_model.name}")
            
            with open(latest_model, 'rb') as f:
                return pickle.load(f)
        
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise
    
    def clean_data(self, df):
        """Clean and preprocess the data."""
        logger.info("Cleaning and preprocessing data...")
        
        df = df.copy()
        
        # Clean TotalCharges
        df['TotalCharges'] = df['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
        df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
        total_charges_median = df['TotalCharges'].median()
        df['TotalCharges'].fillna(total_charges_median, inplace=True)
        
        # Convert dtypes
        df['SeniorCitizen'] = df['SeniorCitizen'].astype(np.int8)
        df['tenure'] = df['tenure'].astype(np.int16)
        
        # Convert categorical columns
        categorical_cols = [
            'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
            'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
            'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
            'PaperlessBilling', 'PaymentMethod'
        ]
        for col in categorical_cols:
            df[col] = df[col].astype('category')
        
        return df
    
    def prepare_features(self, df):
        """Prepare features for prediction."""
        logger.info("Preparing features...")
        
        # Drop customerID if present
        if 'customerID' in df.columns:
            df = df.drop('customerID', axis=1)
        
        # Drop Churn column if present (for new data)
        if 'Churn' in df.columns:
            df = df.drop('Churn', axis=1)
        
        # Convert categorical variables
        X = pd.get_dummies(df)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, X.columns
    
    def get_feature_importance_explanations(self, X_scaled, feature_names):
        """Generate feature importance explanations for predictions."""
        logger.info("Generating feature importance explanations...")
        try:
            # Get feature importances based on model type
            if isinstance(self.model, xgb.XGBClassifier):
                importances = self.model.feature_importances_
            elif isinstance(self.model, LogisticRegression):
                importances = np.abs(self.model.coef_[0])
            else:
                # For other models that might not have feature_importances_
                return ["Feature importance not available for this model type"] * len(X_scaled)
            
            # Get indices of top features for each prediction
            top_features = []
            for _ in range(len(X_scaled)):
                # Get indices of top 3 features
                top_indices = np.argsort(importances)[-3:][::-1]
                
                # Create explanation string
                features = []
                for idx in top_indices:
                    feature = feature_names[idx]
                    importance = importances[idx]
                    impact = "increases" if importance > 0 else "decreases"
                    features.append(f"{feature} {impact} retention by {abs(importance):.3f}")
                
                top_features.append("; ".join(features))
            
            return top_features
        
        except Exception as e:
            logger.error(f"Error generating feature importance explanations: {str(e)}")
            raise
    
    def predict(self, df):
        """Make predictions on the input data."""
        try:
            # Store customerID if present
            customer_ids = df['customerID'].copy() if 'customerID' in df.columns else None
            
            # Clean data
            df_cleaned = self.clean_data(df)
            
            # Prepare features
            X_scaled, feature_names = self.prepare_features(df_cleaned)
            
            # Make predictions
            logger.info("Making predictions...")
            y_pred_proba = self.model.predict_proba(X_scaled)[:, 1]
            # Convert churn probability to retention probability
            retention_proba = 1 - y_pred_proba
            retention_pred = (retention_proba >= 0.5).astype(int)
            
            # Generate feature importance explanations
            top_features = self.get_feature_importance_explanations(X_scaled, feature_names)
            
            # Create results dataframe
            results = pd.DataFrame({
                'retention_probability': retention_proba,
                'retention_prediction': retention_pred,
                'feature_importance': top_features
            })
            
            # Add back original features and customerID
            if customer_ids is not None:
                results = pd.concat([
                    pd.DataFrame({'customerID': customer_ids}),
                    df_cleaned,
                    results
                ], axis=1)
            else:
                results = pd.concat([df_cleaned, results], axis=1)
            
            return results
        
        except Exception as e:
            logger.error(f"Error during prediction: {str(e)}")
            raise
    
    def save_predictions(self, df, upload_id):
        """Save predictions to CSV file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.predictions_dir / f"{upload_id}_predicted_{timestamp}.csv"
            
            df.to_csv(output_path, index=False)
            logger.info(f"Predictions saved to: {output_path}")
            
            return output_path
        
        except Exception as e:
            logger.error(f"Error saving predictions: {str(e)}")
            raise 