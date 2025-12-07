# Sample CSV Files for RetainWise

These sample CSV files help you test the RetainWise churn prediction system with realistic data.

## Files

### 1. sample_telecom.csv
- **Industry:** Telecommunications / Internet Service Providers
- **Rows:** 10 sample customers
- **Use Case:** Predict customer churn for telecom companies
- **Required Columns:** customerID, tenure, MonthlyCharges, TotalCharges, Contract
- **Optional Columns:** 15 additional demographic and service features

### 2. sample_saas.csv
- **Industry:** SaaS (Software as a Service) B2B companies
- **Rows:** 10 sample accounts
- **Use Case:** Predict subscription churn for SaaS platforms
- **Required Columns:** user_id, months_subscribed, mrr, total_revenue, plan_type
- **Optional Columns:** 12 additional usage and engagement features

## How to Use

1. **Download** the sample CSV for your industry
2. **Review** the data structure and column names
3. **Replace** sample data with your actual customer data
4. **Upload** to RetainWise for churn predictions

## Column Name Flexibility

**Good news:** You don't need to match our exact column names! 

Our intelligent column mapper automatically detects variations:

| Your Column Name | We Recognize As |
|------------------|-----------------|
| `customer_id`, `Customer ID`, `cust_id`, `user_id` | customerID |
| `months_active`, `tenure_months`, `account_age` | tenure |
| `monthly_fee`, `mrr`, `monthly_revenue` | MonthlyCharges |
| `ltv`, `lifetime_value`, `total_spent` | TotalCharges |
| `plan_type`, `contract_type`, `subscription_type` | Contract |

**200+ variations supported per column!**

Just upload your CSV and we'll handle the rest.

## Data Format Tips

- ✅ **File format:** CSV (comma-separated values)
- ✅ **First row:** Column headers (not data)
- ✅ **Encoding:** UTF-8 (Excel default is fine)
- ✅ **Numbers:** Use decimals (29.99) not currency symbols ($29.99)
- ✅ **Dates:** Any standard format works (we auto-detect)

## Common Export Sources

Our mapper works with CSVs from:
- ✅ Stripe
- ✅ Chargebee
- ✅ ChartMogul
- ✅ Baremetrics
- ✅ ProfitWell
- ✅ Custom database exports
- ✅ Excel spreadsheets

## Need Help?

If your CSV doesn't upload successfully:
1. Check file is in CSV format (not .xlsx)
2. Verify first row contains column headers
3. Ensure required columns are present
4. Check for special characters in data

Contact: support@retainwiseanalytics.com

---

**Pro Tip:** Download both samples to see the difference between Telecom and SaaS churn indicators!

