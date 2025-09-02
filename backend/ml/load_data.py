import os
import pandas as pd
from pathlib import Path
import sys

def load_telco_data():
    """
    Load the Telco Customer Churn dataset with proper data types and error handling.
    Returns:
        pandas.DataFrame or None: The loaded dataset if successful, None otherwise
    """
    try:
        # Define the data path using pathlib for cross-platform compatibility
        data_path = Path(__file__).parent / "data" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
        
        # Check if file exists using os.path
        if not os.path.exists(data_path):
            raise FileNotFoundError(
                f"Dataset not found at {data_path}. "
                "Please ensure the file is in the correct location."
            )

        # Define data types for specific columns
        dtype_dict = {
            'SeniorCitizen': 'int8',
            'TotalCharges': 'object'  # Keep as object for now, will clean later
        }

        # Load the dataset with specified data types
        df = pd.read_csv(
            data_path,
            dtype=dtype_dict
        )

        # Print success message with shape
        print(f"\nDataset loaded successfully!")
        print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        
        # Print first 3 rows for verification
        print("\nFirst 3 rows for verification:")
        print("------------------------------")
        print(df.head(3))
        
        return df

    except FileNotFoundError as e:
        print(f"\nError: {str(e)}", file=sys.stderr)
        print("\nDebug steps:", file=sys.stderr)
        print("1. Verify the file exists in the 'backend/ml/data' directory", file=sys.stderr)
        print("2. Check file permissions", file=sys.stderr)
        return None

    except pd.errors.EmptyDataError:
        print("\nError: The CSV file is empty.", file=sys.stderr)
        print("\nDebug steps:", file=sys.stderr)
        print("1. Verify the file contains data", file=sys.stderr)
        print("2. Try opening the file in a text editor", file=sys.stderr)
        return None

    except pd.errors.ParserError as e:
        print(f"\nError: Failed to parse CSV file: {str(e)}", file=sys.stderr)
        print("\nDebug steps:", file=sys.stderr)
        print("1. Check if the file is a valid CSV", file=sys.stderr)
        print("2. Look for special characters or encoding issues", file=sys.stderr)
        print("3. Verify the CSV delimiter is correct", file=sys.stderr)
        return None

    except Exception as e:
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        print("Please report this error with the full traceback", file=sys.stderr)
        return None

if __name__ == "__main__":
    # Try to load the dataset
    df = load_telco_data()
    
    if df is not None:
        # Additional verification
        print("\nData Types:")
        print("-----------")
        print(df.dtypes[['SeniorCitizen', 'TotalCharges']])  # Verify specified dtypes 
