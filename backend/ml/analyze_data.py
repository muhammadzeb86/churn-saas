import pandas as pd
import numpy as np
from pathlib import Path

def load_cleaned_data():
    """Load the cleaned Telco Customer Churn dataset."""
    data_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-CLEANED.csv"
    return pd.read_csv(data_path)

def analyze_churn_distribution(df):
    """Analyze and format churn distribution."""
    churn_dist = df['Churn'].value_counts()
    churn_pct = df['Churn'].value_counts(normalize=True) * 100
    
    report = ["1. Churn Distribution", "-" * 20]
    report.append("\nRaw Counts:")
    for label, count in churn_dist.items():
        report.append(f"{label}: {count:,}")
    
    report.append("\nPercentages:")
    for label, pct in churn_pct.items():
        report.append(f"{label}: {pct:.2f}%")
    
    return "\n".join(report)

def analyze_numeric_features(df):
    """Analyze numeric features statistics."""
    numeric_cols = ['tenure', 'MonthlyCharges', 'TotalCharges']
    stats = df[numeric_cols].agg([
        'mean', 'min', 'max',
        lambda x: x.quantile(0.25),
        'median',
        lambda x: x.quantile(0.75)
    ]).round(2)
    
    stats.index = ['Mean', 'Min', 'Max', '25th Percentile', 'Median', '75th Percentile']
    
    report = ["\n2. Numeric Features Statistics", "-" * 20]
    for col in numeric_cols:
        report.append(f"\n{col}:")
        for stat_name, value in stats[col].items():
            report.append(f"{stat_name}: {value:,.2f}")
    
    return "\n".join(report)

def analyze_categorical_features(df):
    """Analyze categorical features and their relationship with churn."""
    categorical_cols = [
        'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
        'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
        'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
        'PaperlessBilling', 'PaymentMethod'
    ]
    
    report = ["\n3. Categorical Features Analysis", "-" * 20]
    
    # Unique value counts
    report.append("\nUnique Values per Category:")
    for col in categorical_cols:
        unique_count = df[col].nunique()
        report.append(f"{col}: {unique_count} unique values")
    
    # Churn rates by category
    report.append("\nChurn Rates by Category:")
    for col in categorical_cols:
        report.append(f"\n{col}:")
        churn_rates = df.groupby(col)['Churn'].apply(
            lambda x: (x == 'Yes').mean() * 100
        ).round(2)
        for category, rate in churn_rates.items():
            report.append(f"{category}: {rate:.2f}% churn rate")
    
    return "\n".join(report)

def main():
    # Load data
    df = load_cleaned_data()
    
    # Generate report sections
    report_sections = [
        analyze_churn_distribution(df),
        analyze_numeric_features(df),
        analyze_categorical_features(df)
    ]
    
    # Combine full report
    full_report = "\nTELCO CUSTOMER CHURN - EDA REPORT\n" + "=" * 40 + "\n"
    full_report += "\n".join(report_sections)
    
    # Save report
    report_path = Path(__file__).parent / "reports"
    report_path.mkdir(exist_ok=True)
    with open(report_path / "eda_summary.txt", "w") as f:
        f.write(full_report)
    
    print("EDA report has been generated and saved to reports/eda_summary.txt")

if __name__ == "__main__":
    main() 