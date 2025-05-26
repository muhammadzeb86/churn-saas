import pandas as pd
from pathlib import Path

# Load the dataset using relative path
data_path = Path(__file__).parent / "data" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
print(f"Loading data from: {data_path}")
df = pd.read_csv(data_path)

# Convert TotalCharges to numeric, handling any spaces
df['TotalCharges'] = pd.to_numeric(df['TotalCharges'].str.strip(), errors='coerce')

# Print dataset shape
print("\nDataset Shape:")
print("--------------")
print(f"Rows: {df.shape[0]}")
print(f"Columns: {df.shape[1]}")

# Print column names and data types
print("\nColumn Names and Data Types:")
print("--------------------------")
for col, dtype in df.dtypes.items():
    print(f"{col:<20} {dtype}")

# Print missing values per column
print("\nMissing Values per Column:")
print("-------------------------")
missing_values = df.isnull().sum()
for col in df.columns:
    if missing_values[col] > 0:
        percentage = (missing_values[col] / len(df) * 100)
        print(f"{col:<20} {missing_values[col]:>5} ({percentage:>5.2f}%)")

# Print value counts of target column
print("\nChurn Distribution:")
print("------------------")
churn_counts = df['Churn'].value_counts()
total = len(df)
for label, count in churn_counts.items():
    percentage = (count / total * 100)
    print(f"{label:<5} {count:>5} ({percentage:>5.2f}%)") 