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
        
        # Try to load the latest model, but don't fail if none exists
        try:
            self.model = self._load_latest_model()
            self.model_available = True
        except FileNotFoundError:
            logger.warning("No model files found. Predictor will not be functional until a model is available.")
            self.model = None
            self.model_available = False
        
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
        """
        Clean and preprocess the data.
        
        Handles missing columns gracefully for both Telecom and SaaS industries.
        Columns are expected to be already standardized by IntelligentColumnMapper.
        """
        logger.info("Cleaning and preprocessing data...")
        
        df = df.copy()
        
        # Clean TotalCharges (if present)
        if 'TotalCharges' in df.columns:
            df['TotalCharges'] = df['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
            df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
            total_charges_median = df['TotalCharges'].median()
            df['TotalCharges'].fillna(total_charges_median, inplace=True)
            logger.info("TotalCharges column cleaned")
        else:
            logger.warning("TotalCharges column not found - skipping cleaning")
        
        # Convert dtypes (only if columns exist)
        if 'SeniorCitizen' in df.columns:
            try:
                df['SeniorCitizen'] = df['SeniorCitizen'].astype(np.int8)
                logger.info("SeniorCitizen column converted to int8")
            except Exception as e:
                logger.warning(f"Could not convert SeniorCitizen to int8: {str(e)}")
        else:
            logger.info("SeniorCitizen column not found - optional column, skipping")
        
        if 'tenure' in df.columns:
            try:
                df['tenure'] = df['tenure'].astype(np.int16)
                logger.info("tenure column converted to int16")
            except Exception as e:
                logger.error(f"Could not convert tenure to int16: {str(e)}")
                raise ValueError("Required column 'tenure' has invalid data type")
        else:
            logger.error("Required column 'tenure' is missing")
            raise ValueError("Required column 'tenure' is missing after column mapping")
        
        # Convert categorical columns (only if present)
        categorical_cols = [
            'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
            'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
            'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
            'PaperlessBilling', 'PaymentMethod'
        ]
        
        found_categorical = 0
        for col in categorical_cols:
            if col in df.columns:
                try:
                    df[col] = df[col].astype('category')
                    found_categorical += 1
                except Exception as e:
                    logger.warning(f"Could not convert {col} to category: {str(e)}")
            # No warning for missing optional columns - this is normal for SaaS
        
        logger.info(f"Data cleaning complete: {found_categorical}/{len(categorical_cols)} optional categorical columns found")
        
        return df
    
    def prepare_features(self, df):
        """
        Prepare features for prediction with SaaS-to-Telecom alignment.
        
        The model was trained on Telecom data (45 features).
        This method aligns SaaS data to match Telecom features.
        """
        logger.info("Preparing features for prediction...")
        
        # Drop customerID if present
        if 'customerID' in df.columns:
            df = df.drop('customerID', axis=1)
        
        # Drop Churn column if present (for new data)
        if 'Churn' in df.columns:
            df = df.drop('Churn', axis=1)
        
        # ========================================
        # SAAS-TO-TELECOM FEATURE ALIGNMENT
        # ========================================
        # The model expects Telecom features but receives SaaS data
        # We need to add/map missing Telecom features
        
        # Required Telecom categorical features that model expects
        telecom_required_features = {
            'gender': 'Male',  # Default
            'SeniorCitizen': 0,  # Default: Not senior
            'Partner': 'No',  # Default
            'Dependents': 'No',  # Default
            'PhoneService': 'Yes',  # Default: Has phone
            'MultipleLines': 'No',  # Default
            'InternetService': 'Fiber optic',  # Default: Premium service (SaaS assumption)
            'OnlineSecurity': 'No',  # Default
            'OnlineBackup': 'No',  # Default
            'DeviceProtection': 'No',  # Default
            'TechSupport': 'No',  # Default
            'StreamingTV': 'No',  # Default
            'StreamingMovies': 'No',  # Default
            'PaperlessBilling': 'Yes',  # Default: Modern/SaaS companies use digital
            'PaymentMethod': 'Electronic check'  # Default
        }
        
        # Add missing Telecom features with defaults
        for feature, default_value in telecom_required_features.items():
            if feature not in df.columns:
                df[feature] = default_value
                logger.info(f"Added missing Telecom feature: {feature} = {default_value}")
        
        # Convert categorical variables to one-hot encoding
        X = pd.get_dummies(df)
        
        logger.info(f"Features after one-hot encoding: {X.shape[1]} features")
        
        # ========================================
        # FEATURE MATCHING TO MODEL EXPECTATIONS
        # ========================================
        # The model was trained on specific feature names
        # We need to ensure we have exactly those features
        
        # Expected features from Telecom model (45 features)
        # This is the feature set the model was trained on
        expected_features = [
            'tenure', 'MonthlyCharges', 'TotalCharges', 'SeniorCitizen',
            'gender_Female', 'gender_Male',
            'Partner_No', 'Partner_Yes',
            'Dependents_No', 'Dependents_Yes',
            'PhoneService_No', 'PhoneService_Yes',
            'MultipleLines_No', 'MultipleLines_No phone service', 'MultipleLines_Yes',
            'InternetService_DSL', 'InternetService_Fiber optic', 'InternetService_No',
            'OnlineSecurity_No', 'OnlineSecurity_No internet service', 'OnlineSecurity_Yes',
            'OnlineBackup_No', 'OnlineBackup_No internet service', 'OnlineBackup_Yes',
            'DeviceProtection_No', 'DeviceProtection_No internet service', 'DeviceProtection_Yes',
            'TechSupport_No', 'TechSupport_No internet service', 'TechSupport_Yes',
            'StreamingTV_No', 'StreamingTV_No internet service', 'StreamingTV_Yes',
            'StreamingMovies_No', 'StreamingMovies_No internet service', 'StreamingMovies_Yes',
            'Contract_Month-to-month', 'Contract_One year', 'Contract_Two year',
            'PaperlessBilling_No', 'PaperlessBilling_Yes',
            'PaymentMethod_Bank transfer (automatic)', 'PaymentMethod_Credit card (automatic)',
            'PaymentMethod_Electronic check', 'PaymentMethod_Mailed check'
        ]
        
        # Add missing features with zeros
        for feature in expected_features:
            if feature not in X.columns:
                X[feature] = 0
                logger.debug(f"Added missing model feature: {feature} = 0")
        
        # Remove extra features not in expected list
        extra_features = [col for col in X.columns if col not in expected_features]
        if extra_features:
            logger.info(f"Removing {len(extra_features)} extra features not in model: {extra_features[:5]}...")
            X = X[expected_features]
        
        # Ensure correct order (model expects specific order)
        X = X[expected_features]
        
        logger.info(f"Final feature count: {X.shape[1]} (expected: {len(expected_features)})")
        
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
        if not self.model_available:
            raise ValueError("No model available for predictions. Please train and save a model first.")
            
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
