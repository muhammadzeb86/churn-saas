import pandas as pd
import numpy as np
from pathlib import Path

def load_data():
    """Load the cleaned dataset."""
    data_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-CLEANED.csv"
    return pd.read_csv(data_path)

def get_memory_usage(df):
    """Get memory usage of dataframe in MB."""
    return df.memory_usage(deep=True).sum() / (1024 * 1024)

def print_dtype_info(df, title):
    """Print detailed dtype information."""
    print(f"\n{title}")
    print("-" * 40)
    for col in df.columns:
        print(f"{col}: {df[col].dtype}")

def optimize_numeric_types(df):
    """Downcast numeric columns to smallest possible type."""
    df_opt = df.copy()
    
    # Dictionary to store dtype changes
    dtype_changes = {}
    
    for col in df.columns:
        col_type = df[col].dtype
        
        # Handle integer columns
        if col_type == 'int64':
            col_min = df[col].min()
            col_max = df[col].max()
            
            # Test different integer types
            if col_min >= -128 and col_max <= 127:
                df_opt[col] = df[col].astype(np.int8)
                dtype_changes[col] = 'int64 → int8'
            elif col_min >= -32768 and col_max <= 32767:
                df_opt[col] = df[col].astype(np.int16)
                dtype_changes[col] = 'int64 → int16'
            elif col_min >= -2147483648 and col_max <= 2147483647:
                df_opt[col] = df[col].astype(np.int32)
                dtype_changes[col] = 'int64 → int32'
        
        # Handle float columns
        elif col_type == 'float64':
            df_opt[col] = df[col].astype(np.float32)
            dtype_changes[col] = 'float64 → float32'
        
        # Handle object columns (convert to category if fewer than 50% unique values)
        elif col_type == 'object':
            unique_ratio = df[col].nunique() / len(df)
            if unique_ratio < 0.5:  # If less than 50% unique values
                df_opt[col] = df[col].astype('category')
                dtype_changes[col] = 'object → category'
    
    return df_opt, dtype_changes

def main():
    # Load data
    print("Loading data...")
    df = load_data()
    
    # Get initial memory usage
    initial_mem = get_memory_usage(df)
    print(f"\nInitial memory usage: {initial_mem:.2f} MB")
    print_dtype_info(df, "Initial dtypes:")
    
    # Optimize datatypes
    print("\nOptimizing datatypes...")
    df_optimized, dtype_changes = optimize_numeric_types(df)
    
    # Get optimized memory usage
    final_mem = get_memory_usage(df_optimized)
    print(f"\nFinal memory usage: {final_mem:.2f} MB")
    print(f"Memory reduced by: {(initial_mem - final_mem):.2f} MB ({((initial_mem - final_mem)/initial_mem)*100:.1f}%)")
    
    # Print dtype changes
    print("\nDtype changes made:")
    print("-" * 40)
    for col, change in dtype_changes.items():
        print(f"{col}: {change}")
    
    print_dtype_info(df_optimized, "\nFinal dtypes:")
    
    # Save optimized dataset
    output_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-OPTIMIZED.csv"
    df_optimized.to_csv(output_path, index=False)
    print(f"\nOptimized dataset saved to:\n{output_path}")

if __name__ == "__main__":
    main() 