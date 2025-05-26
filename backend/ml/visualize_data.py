import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# Set the style
sns.set_theme(style="whitegrid")  # Use seaborn's whitegrid style
FIGSIZE = (10, 6)
DPI = 300

def load_cleaned_data():
    """Load the cleaned Telco Customer Churn dataset."""
    data_path = Path(__file__).parent / "data" / "Telco-Customer-Churn-CLEANED.csv"
    return pd.read_csv(data_path)

def create_plots_directory():
    """Create plots directory if it doesn't exist."""
    plots_dir = Path(__file__).parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    return plots_dir

def plot_churn_distribution(df, plots_dir):
    """Create bar plot of churn distribution."""
    plt.figure(figsize=FIGSIZE)
    
    # Calculate counts and percentages
    churn_counts = df['Churn'].value_counts()
    churn_pcts = df['Churn'].value_counts(normalize=True) * 100
    
    # Create bar plot
    ax = sns.barplot(x=churn_counts.index, y=churn_counts.values)
    
    # Add percentage labels on top of bars
    for i, (count, pct) in enumerate(zip(churn_counts, churn_pcts)):
        ax.text(i, count, f'{count:,}\n({pct:.1f}%)', 
                ha='center', va='bottom')
    
    plt.title('Customer Churn Distribution', fontsize=14)
    plt.xlabel('Churn Status')
    plt.ylabel('Number of Customers')
    
    # Save plot
    plt.savefig(plots_dir / 'churn_distribution.png', dpi=DPI, bbox_inches='tight')
    plt.close()

def plot_tenure_distribution(df, plots_dir):
    """Create histogram with KDE for tenure distribution."""
    plt.figure(figsize=FIGSIZE)
    
    # Create histogram with KDE
    sns.histplot(data=df, x='tenure', bins=30, kde=True)
    
    plt.title('Customer Tenure Distribution', fontsize=14)
    plt.xlabel('Tenure (months)')
    plt.ylabel('Count')
    
    # Save plot
    plt.savefig(plots_dir / 'tenure_distribution.png', dpi=DPI, bbox_inches='tight')
    plt.close()

def plot_charges_boxplot(df, plots_dir):
    """Create boxplot comparing Monthly and Total Charges."""
    plt.figure(figsize=FIGSIZE)
    
    # Prepare data for boxplot
    charges_data = pd.DataFrame({
        'Monthly Charges': df['MonthlyCharges'],
        'Total Charges': df['TotalCharges'] / df['tenure'].clip(lower=1)  # Normalize by tenure
    })
    
    # Create boxplot
    sns.boxplot(data=charges_data)
    
    plt.title('Monthly vs Normalized Total Charges Distribution', fontsize=14)
    plt.ylabel('Charges ($)')
    
    # Save plot
    plt.savefig(plots_dir / 'charges_boxplot.png', dpi=DPI, bbox_inches='tight')
    plt.close()

def plot_correlation_heatmap(df, plots_dir):
    """Create correlation heatmap for numeric features."""
    plt.figure(figsize=FIGSIZE)
    
    # Select numeric columns
    numeric_cols = ['tenure', 'MonthlyCharges', 'TotalCharges']
    corr_matrix = df[numeric_cols].corr()
    
    # Create heatmap
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0,
                fmt='.2f', square=True)
    
    plt.title('Correlation Heatmap of Numeric Features', fontsize=14)
    
    # Save plot
    plt.savefig(plots_dir / 'correlation_heatmap.png', dpi=DPI, bbox_inches='tight')
    plt.close()

def main():
    # Load data
    df = load_cleaned_data()
    
    # Create plots directory
    plots_dir = create_plots_directory()
    
    # Generate all plots
    plot_churn_distribution(df, plots_dir)
    plot_tenure_distribution(df, plots_dir)
    plot_charges_boxplot(df, plots_dir)
    plot_correlation_heatmap(df, plots_dir)
    
    print("All visualizations have been generated and saved to the plots directory.")

if __name__ == "__main__":
    main() 