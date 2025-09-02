import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import pickle
import warnings
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import (classification_report, roc_curve, precision_recall_curve,
                           auc, average_precision_score)
from imblearn.over_sampling import SMOTE
import xgboost as xgb

# Suppress warnings
warnings.filterwarnings('ignore')

# Set random seed for reproducibility
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

class ChurnPredictor:
    def __init__(self):
        """Initialize paths and timestamp."""
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_path = Path(__file__).parent
        
        # Create necessary directories
        self.dirs = {
            'data': self.base_path / 'data',
            'models': self.base_path / 'models',
            'plots': self.base_path / 'plots',
            'reports': self.base_path / 'reports'
        }
        for dir_path in self.dirs.values():
            dir_path.mkdir(exist_ok=True)
    
    def log_step(self, message):
        """Print timestamped log message."""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def load_data(self):
        """Load and verify raw data."""
        self.log_step("Loading raw data...")
        
        data_path = self.dirs['data'] / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
        if not data_path.exists():
            raise FileNotFoundError(f"Data file not found at: {data_path}")
        
        df = pd.read_csv(data_path)
        print(f"\nDataset shape: {df.shape}")
        print("\nFirst 3 rows:")
        print(df.head(3))
        
        return df
    
    def clean_data(self, df):
        """Clean and preprocess the data."""
        self.log_step("Cleaning data...")
        
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
            'PaperlessBilling', 'PaymentMethod', 'Churn'
        ]
        for col in categorical_cols:
            df[col] = df[col].astype('category')
        
        # Save cleaned data
        output_path = self.dirs['data'] / f"Telco-Customer-Churn-CLEANED_{self.timestamp}.csv"
        df.to_csv(output_path, index=False)
        print(f"\nCleaned data saved to: {output_path}")
        
        return df
    
    def analyze_data(self, df):
        """Perform EDA and generate visualizations."""
        self.log_step("Performing exploratory data analysis...")
        
        # 1. Churn Distribution
        plt.figure(figsize=(10, 6))
        churn_dist = df['Churn'].value_counts()
        churn_pct = df['Churn'].value_counts(normalize=True) * 100
        
        ax = sns.barplot(x=churn_dist.index, y=churn_dist.values)
        for i, (count, pct) in enumerate(zip(churn_dist, churn_pct)):
            ax.text(i, count, f'{count:,}\n({pct:.1f}%)', ha='center', va='bottom')
        
        plt.title('Customer Churn Distribution', fontsize=14)
        plt.savefig(self.dirs['plots'] / f"churn_distribution_{self.timestamp}.png")
        plt.close()
        
        # 2. Numeric Features Distribution
        numeric_cols = ['tenure', 'MonthlyCharges', 'TotalCharges']
        plt.figure(figsize=(15, 5))
        for i, col in enumerate(numeric_cols, 1):
            plt.subplot(1, 3, i)
            sns.histplot(data=df, x=col, hue='Churn', multiple="stack")
            plt.title(f'{col} Distribution by Churn')
        plt.tight_layout()
        plt.savefig(self.dirs['plots'] / f"numeric_distributions_{self.timestamp}.png")
        plt.close()
        
        # 3. Correlation Heatmap
        plt.figure(figsize=(10, 8))
        correlation = df[numeric_cols].corr()
        sns.heatmap(correlation, annot=True, cmap='coolwarm', center=0)
        plt.title('Feature Correlations', fontsize=14)
        plt.savefig(self.dirs['plots'] / f"correlation_heatmap_{self.timestamp}.png")
        plt.close()
    
    def prepare_features(self, df):
        """Prepare features for modeling."""
        self.log_step("Preparing features...")
        
        # Drop customerID and encode categorical variables
        X = pd.get_dummies(df.drop(['customerID', 'Churn'], axis=1))
        y = (df['Churn'] == 'Yes').astype(int)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        return X_train_scaled, X_test_scaled, y_train, y_test, X.columns
    
    def train_models(self, X_train, X_test, y_train, y_test, feature_names):
        """Train and evaluate multiple models."""
        self.log_step("Training models...")
        
        models = {
            'logistic_vanilla': LogisticRegression(random_state=RANDOM_STATE),
            'logistic_balanced': LogisticRegression(class_weight='balanced', random_state=RANDOM_STATE),
            'logistic_smote': Pipeline([
                ('smote', SMOTE(random_state=RANDOM_STATE)),
                ('classifier', LogisticRegression(random_state=RANDOM_STATE))
            ]),
            'xgboost_vanilla': xgb.XGBClassifier(
                random_state=RANDOM_STATE,
                use_label_encoder=False,
                eval_metric='logloss'
            ),
            'xgboost_weighted': xgb.XGBClassifier(
                scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1]),
                random_state=RANDOM_STATE,
                use_label_encoder=False,
                eval_metric='aucpr'
            )
        }
        
        # Train and evaluate models
        results = []
        best_score = 0
        best_model = None
        
        for name, model in models.items():
            self.log_step(f"Training {name}...")
            
            # Train with cross-validation
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
            cv_scores = []
            
            for fold, (train_idx, val_idx) in enumerate(cv.split(X_train, y_train), 1):
                X_fold_train, X_fold_val = X_train[train_idx], X_train[val_idx]
                y_fold_train, y_fold_val = y_train[train_idx], y_train[val_idx]
                
                model.fit(X_fold_train, y_fold_train)
                y_fold_pred = model.predict(X_fold_val)
                cv_scores.append(average_precision_score(y_fold_val, y_fold_pred))
            
            # Final evaluation on test set
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            report = classification_report(y_test, y_pred)
            avg_cv_score = np.mean(cv_scores)
            
            results.append({
                'name': name,
                'model': model,
                'cv_score': avg_cv_score,
                'report': report
            })
            
            # Track best model
            if avg_cv_score > best_score:
                best_score = avg_cv_score
                best_model = model
        
        return results, best_model
    
    def save_results(self, results, best_model, feature_names):
        """Save model results and performance reports."""
        self.log_step("Saving results...")
        
        # Save performance report
        report_path = self.dirs['reports'] / f"performance_{self.timestamp}.txt"
        with open(report_path, 'w') as f:
            f.write("CHURN PREDICTION MODEL PERFORMANCE\n")
            f.write("=" * 40 + "\n\n")
            
            for result in results:
                f.write(f"\nModel: {result['name']}\n")
                f.write("-" * 40 + "\n")
                f.write(f"CV Score (AUCPR): {result['cv_score']:.4f}\n\n")
                f.write("Classification Report:\n")
                f.write(result['report'])
                f.write("\n" + "=" * 40 + "\n")
        
        # Save best model
        model_path = self.dirs['models'] / f"best_churn_model_{self.timestamp}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(best_model, f)
        
        print(f"\nResults saved to: {report_path}")
        print(f"Best model saved to: {model_path}")
    
    def run_pipeline(self):
        """Run the complete modeling pipeline."""
        try:
            # Load and process data
            df = self.load_data()
            df_cleaned = self.clean_data(df)
            self.analyze_data(df_cleaned)
            
            # Prepare features and train models
            X_train, X_test, y_train, y_test, feature_names = self.prepare_features(df_cleaned)
            results, best_model = self.train_models(X_train, X_test, y_train, y_test, feature_names)
            
            # Save results
            self.save_results(results, best_model, feature_names)
            
            self.log_step("Pipeline completed successfully!")
            
        except Exception as e:
            self.log_step(f"Error: {str(e)}")
            raise

if __name__ == "__main__":
    predictor = ChurnPredictor()
    predictor.run_pipeline() 
