import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime
import zipfile
import os

def load_optimized_data():
    """Load the optimized dataset."""
    data_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-OPTIMIZED.csv"
    return pd.read_csv(data_path)

def create_output_structure():
    """Create timestamped output directory structure."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(__file__).parent / "output" / f"analysis_{timestamp}"
    
    # Create directories
    dirs = {
        'data': base_dir / "data",
        'plots': base_dir / "plots",
        'reports': base_dir / "reports"
    }
    
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return dirs, timestamp

def copy_artifacts(dirs, timestamp):
    """Copy existing artifacts to timestamped directories."""
    # Source directories
    src_dirs = {
        'data': Path(__file__).parent / "data",
        'plots': Path(__file__).parent / "plots",
        'reports': Path(__file__).parent / "reports"
    }
    
    # Copy files with timestamped names
    copied_files = []
    
    # Copy data files
    data_files = [
        "Telco-Customer-Churn-CLEANED.csv",
        "Telco-Customer-Churn-OPTIMIZED.csv"
    ]
    for file in data_files:
        if (src_dirs['data'] / file).exists():
            new_name = f"Telco-Customer-Churn_{timestamp}.csv"
            shutil.copy2(src_dirs['data'] / file, dirs['data'] / new_name)
            copied_files.append(str(dirs['data'] / new_name))
    
    # Copy plots
    plot_files = [
        "churn_distribution.png",
        "tenure_distribution.png",
        "charges_boxplot.png",
        "correlation_heatmap.png"
    ]
    for file in plot_files:
        if (src_dirs['plots'] / file).exists():
            new_name = f"{file.split('.')[0]}_{timestamp}.png"
            shutil.copy2(src_dirs['plots'] / file, dirs['plots'] / new_name)
            copied_files.append(str(dirs['plots'] / new_name))
    
    # Copy reports
    if (src_dirs['reports'] / "eda_summary.txt").exists():
        new_name = f"eda_summary_{timestamp}.txt"
        shutil.copy2(src_dirs['reports'] / "eda_summary.txt", dirs['reports'] / new_name)
        copied_files.append(str(dirs['reports'] / new_name))
    
    return copied_files

def generate_readme(df, dirs, timestamp):
    """Generate README with analysis summary."""
    readme_content = [
        "TELCO CUSTOMER CHURN ANALYSIS",
        "=" * 30,
        f"\nAnalysis Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\nPROCESSING SUMMARY",
        "-" * 20,
        "1. Data Cleaning:",
        "   - Handled missing values in TotalCharges",
        "   - Converted categorical columns to proper dtypes",
        "   - Validated data integrity",
        "\n2. Memory Optimization:",
        f"   - Final dataset size: {df.memory_usage(deep=True).sum() / (1024*1024):.2f} MB",
        "   - Converted numeric columns to smallest possible dtypes",
        "   - Optimized categorical columns",
        "\n3. Visualizations Generated:",
        "   - Churn distribution plot",
        "   - Tenure distribution histogram",
        "   - Charges comparison boxplot",
        "   - Feature correlation heatmap",
        "\nCOLUMN DESCRIPTIONS",
        "-" * 20
    ]
    
    # Add column descriptions
    for col in df.columns:
        unique_vals = df[col].nunique()
        dtype = df[col].dtype
        readme_content.append(f"{col}:")
        readme_content.append(f"   - Type: {dtype}")
        readme_content.append(f"   - Unique values: {unique_vals}")
        if col == 'Churn':
            churn_dist = df[col].value_counts(normalize=True) * 100
            for status, pct in churn_dist.items():
                readme_content.append(f"   - {status}: {pct:.1f}%")
    
    # Write README
    readme_path = dirs['reports'] / f"README_{timestamp}.txt"
    with open(readme_path, 'w') as f:
        f.write('\n'.join(readme_content))
    
    return str(readme_path)

def create_zip_archive(output_dir, timestamp):
    """Create ZIP archive of all artifacts."""
    zip_path = Path(__file__).parent / "output" / "analysis_artifacts.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(output_dir)
                zipf.write(file_path, arcname)
    
    return zip_path

def main():
    # Load optimized data
    print("Loading optimized data...")
    df = load_optimized_data()
    
    # Create output structure
    print("\nCreating output directory structure...")
    dirs, timestamp = create_output_structure()
    
    # Copy artifacts
    print("Copying artifacts with timestamps...")
    copied_files = copy_artifacts(dirs, timestamp)
    
    # Generate README
    print("Generating README...")
    readme_path = generate_readme(df, dirs, timestamp)
    copied_files.append(readme_path)
    
    # Create ZIP archive
    print("\nCreating ZIP archive...")
    zip_path = create_zip_archive(dirs['data'].parent, timestamp)
    
    print(f"\nArtifacts successfully exported and archived to:\n{zip_path}")
    print("\nArchive contents:")
    for file in copied_files:
        print(f"- {Path(file).relative_to(Path(__file__).parent)}")

if __name__ == "__main__":
    main() 