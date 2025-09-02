import pandas as pd
import numpy as np
from pathlib import Path
from backend.ml.load_data import load_telco_data

def clean_telco_data(df):
    """
    Clean and preprocess the Telco Customer Churn dataset.
    
    Args:
        df (pandas.DataFrame): Raw dataframe from load_telco_data()
    
    Returns:
        pandas.DataFrame: Cleaned dataframe
    """
    print("\nStarting data cleaning process...")
    
    # Store original shape for verification
    original_shape = df.shape
    
    # 1. Handle TotalCharges conversion
    print("\nCleaning TotalCharges column...")
    # Replace empty strings and spaces with NaN
    df['TotalCharges'] = df['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
    # Convert to float64
    df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
    # Fill NaN with median
    total_charges_median = df['TotalCharges'].median()
    df['TotalCharges'] = df['TotalCharges'].fillna(total_charges_median)
    print(f"- Filled {df['TotalCharges'].isna().sum()} missing values with median: {total_charges_median:.2f}")
    
    # 2. Convert categorical columns
    categorical_columns = [
        'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
        'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
        'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
        'PaperlessBilling', 'PaymentMethod', 'Churn'
    ]
    
    print("\nConverting categorical columns...")
    for col in categorical_columns:
        df[col] = df[col].astype('category')
        print(f"- {col}: {len(df[col].cat.categories)} unique categories")
    
    # 3. Validation checks
    print("\nPerforming validation checks...")
    
    # Check for null values
    null_counts = df.isnull().sum()
    if null_counts.any():
        print("\nWarning: Found null values after cleaning:")
        print(null_counts[null_counts > 0])
    else:
        print("✓ No null values found in the cleaned dataset")
    
    # Verify final shape
    print(f"\nOriginal shape: {original_shape}")
    print(f"Final shape: {df.shape}")
    
    # Print detailed information about the cleaned dataset
    print("\nDetailed Dataset Information:")
    print("-" * 40)
    df.info(show_counts=True)
    
    return df

def save_cleaned_data(df, output_path):
    """Save the cleaned dataset to CSV."""
    try:
        df.to_csv(output_path, index=False)
        print(f"\nCleaned dataset saved successfully to:\n{output_path}")
        print(f"File size: {output_path.stat().st_size / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"\nError saving cleaned dataset: {str(e)}")

if __name__ == "__main__":
    # Load the raw dataset
    raw_df = load_telco_data()
    
    if raw_df is not None:
        # Clean the dataset
        cleaned_df = clean_telco_data(raw_df)
        
        # Save cleaned dataset
        output_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-CLEANED.csv"
        save_cleaned_data(cleaned_df, output_path)
        
        # Print sample of cleaned data
        print("\nSample of cleaned data:")
        print("-" * 40)
        print(cleaned_df.head(3)) 
