#!/usr/bin/env python3
"""
Simple ML Model Training Script for Production
Trains XGBoost churn prediction model without visualization dependencies
"""
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import warnings

warnings.filterwarnings('ignore')

def log_step(message):
    """Print timestamped log message."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {message}")

def train_model():
    """Train churn prediction model."""
    log_step("Starting model training...")
    
    # Paths
    base_path = Path(__file__).parent
    data_path = base_path / 'data' / 'WA_Fn-UseC_-Telco-Customer-Churn.csv'
    model_dir = base_path / 'models'
    model_dir.mkdir(exist_ok=True)
    
    # Load data
    log_step(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Clean TotalCharges
    log_step("Cleaning data...")
    df['TotalCharges'] = df['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
    df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
    df['TotalCharges'].fillna(df['TotalCharges'].median(), inplace=True)
    
    # Prepare features
    log_step("Preparing features...")
    X = pd.get_dummies(df.drop(['customerID', 'Churn'], axis=1))
    y = (df['Churn'] == 'Yes').astype(int)
    
    print(f"Features: {X.shape[1]}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Scale features
    log_step("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    log_step("Training XGBoost model...")
    scale_pos_weight = len(y_train[y_train==0]) / len(y_train[y_train==1])
    
    model = xgb.XGBClassifier(
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='aucpr'
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    log_step("Evaluating model...")
    train_score = model.score(X_train_scaled, y_train)
    test_score = model.score(X_test_scaled, y_test)
    
    print(f"Train accuracy: {train_score:.4f}")
    print(f"Test accuracy: {test_score:.4f}")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)
    print(f"CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Save model
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = model_dir / f"best_retention_model_{timestamp}.pkl"
    
    log_step(f"Saving model to {model_path}")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    # Also save scaler for future use
    scaler_path = model_dir / f"scaler_{timestamp}.pkl"
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save feature names
    feature_path = model_dir / f"features_{timestamp}.txt"
    with open(feature_path, 'w') as f:
        f.write('\n'.join(X.columns))
    
    log_step("Model training completed successfully!")
    print(f"\nModel saved to: {model_path}")
    print(f"Scaler saved to: {scaler_path}")
    print(f"Features saved to: {feature_path}")
    
    return model_path

if __name__ == "__main__":
    try:
        model_path = train_model()
        print(f"\n✅ SUCCESS: Model ready for deployment")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        raise

