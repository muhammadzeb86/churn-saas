# 🎯 Phase 1.7: Train SaaS-Specific ML Model

**Date Created:** December 7, 2025  
**Status:** 📋 **PLANNING** → Ready for Implementation  
**Priority:** P1 - HIGH (Long-term permanent solution)  
**Estimated Time:** 20-24 hours  
**Type:** ML Model Development

---

## 📊 **EXECUTIVE SUMMARY**

### **Current Situation (Temporary Workaround):**
- ❌ Using Telecom-trained model for SaaS predictions
- ❌ Feature alignment layer bridges the gap
- ❌ Not optimal: SaaS data forced into Telecom feature space
- ❌ Prediction accuracy compromised

### **Permanent Solution:**
- ✅ Train dedicated SaaS-specific churn prediction model
- ✅ Native SaaS features (MRR, seats, API calls, usage)
- ✅ Better predictions for SaaS companies
- ✅ No feature alignment needed
- ✅ Highway-grade, production-ready

---

## 🎯 **BUSINESS JUSTIFICATION**

### **Why We Need This:**

1. **Better Accuracy**
   - Current: 76% accuracy (Telecom model on SaaS data)
   - Target: 85%+ accuracy (SaaS-specific model)
   - Impact: Better predictions = higher customer value

2. **SaaS-Specific Insights**
   - Features: MRR growth, feature usage, support tickets
   - Not: Phone service, internet type (irrelevant for SaaS)
   - Impact: Actionable insights for SaaS companies

3. **Competitive Advantage**
   - Marketing: "ML model trained specifically on SaaS data"
   - Credibility: "Built for SaaS, optimized for SaaS"
   - Differentiation: Not a generic tool adapted for SaaS

4. **Scalability**
   - Clean architecture: SaaS model for SaaS data
   - Future: Can add more industry-specific models
   - Maintenance: Easier to improve SaaS-specific features

5. **Product Quality**
   - No workarounds or hacks
   - Native SaaS support
   - Highway-grade quality

---

## 📋 **IMPLEMENTATION PLAN**

### **Task 1.7: Train SaaS-Specific Model** (20-24 hours)

#### **Subtask 1.7.1: Data Collection & Preparation** (6 hours)

**Data Sources:**
1. **Synthetic SaaS Data Generation**
   - Create realistic SaaS customer dataset (10,000+ rows)
   - Features: MRR, seats, usage, support tickets, etc.
   - Churn labels based on industry patterns
   - Tools: Python Faker, numpy, pandas

2. **Public SaaS Datasets**
   - Search for open-source SaaS churn datasets
   - Kaggle, UCI ML Repository, GitHub
   - Combine with synthetic data

3. **Sample Data Expansion**
   - Expand our sample SaaS CSV (10 rows → 10,000 rows)
   - Realistic variations, noise, patterns
   - Proper churn rate distribution (~5-7% for SaaS)

**Data Schema:**

```python
# Required Features (5)
- customerID: str (unique identifier)
- tenure: int (months subscribed)
- MonthlyCharges: float (MRR in dollars)
- TotalCharges: float (lifetime value)
- Contract: str (Month-to-month, Quarterly, Annual)

# SaaS-Specific Features (12+)
- company_size: str (Small, Medium, Large, Enterprise)
- industry: str (SaaS, Fintech, Healthcare, E-commerce, etc.)
- feature_usage_score: float (0-100, usage intensity)
- support_tickets: int (count in last 30 days)
- login_frequency: int (logins per month)
- api_calls_per_month: int (API usage)
- seats_purchased: int (license seats)
- seats_used: int (active users)
- last_activity_days_ago: int (days since last login)
- has_integration: bool (connected to other tools)
- payment_method: str (Credit Card, Bank Transfer, etc.)
- trial_converted: bool (was free trial converted)

# Target
- Churn: int (0 = retained, 1 = churned)
```

**Data Quality Checks:**
- ✅ No missing values in required features
- ✅ Realistic distributions (MRR, tenure, etc.)
- ✅ Proper churn rate (~5-7% for B2B SaaS)
- ✅ Balanced dataset (stratified sampling)
- ✅ No data leakage

**Deliverables:**
- `saas_training_data.csv` (10,000+ rows)
- `saas_test_data.csv` (2,000+ rows, holdout)
- Data quality report

---

#### **Subtask 1.7.2: Model Training & Evaluation** (8 hours)

**Training Approach:**

```python
# backend/ml/train_saas_model.py

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
from datetime import datetime
import pickle

def train_saas_churn_model():
    """
    Train SaaS-specific churn prediction model.
    """
    # Load data
    df = pd.read_csv('data/saas_training_data.csv')
    
    # Feature engineering
    df['mrr_per_seat'] = df['MonthlyCharges'] / df['seats_purchased']
    df['seat_utilization'] = df['seats_used'] / df['seats_purchased']
    df['revenue_per_day_active'] = df['TotalCharges'] / (df['tenure'] * 30 - df['last_activity_days_ago'])
    
    # Prepare features
    X = df.drop(['customerID', 'Churn'], axis=1)
    y = df['Churn']
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    # Encode categorical variables
    X_train_encoded = pd.get_dummies(X_train)
    X_test_encoded = pd.get_dummies(X_test)
    
    # Align columns
    X_train_encoded, X_test_encoded = X_train_encoded.align(
        X_test_encoded, join='left', axis=1, fill_value=0
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_encoded)
    X_test_scaled = scaler.transform(X_test_encoded)
    
    # Train XGBoost model
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss'
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print(f"Model Performance:")
    print(f"Accuracy: {accuracy:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1 Score: {f1:.3f}")
    print(f"AUC-ROC: {auc:.3f}")
    
    # Save model
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = f'backend/ml/models/saas_churn_model_{timestamp}.pkl'
    
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'scaler': scaler,
            'feature_names': X_train_encoded.columns.tolist(),
            'metrics': {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'auc_roc': auc
            }
        }, f)
    
    print(f"Model saved: {model_path}")
    
    return model, scaler, X_train_encoded.columns
```

**Model Evaluation Criteria:**

| Metric | Target | Current (Telecom) | Expected (SaaS) |
|--------|--------|-------------------|-----------------|
| Accuracy | 85%+ | 76% | 85-90% |
| Precision | 80%+ | 72% | 82-88% |
| Recall | 75%+ | 68% | 78-85% |
| F1 Score | 80%+ | 70% | 80-86% |
| AUC-ROC | 85%+ | 78% | 86-92% |

**Deliverables:**
- Trained model file: `saas_churn_model_YYYYMMDD.pkl`
- Training metrics report
- Feature importance analysis
- Model card (documentation)

---

#### **Subtask 1.7.3: Integration & Deployment** (4 hours)

**Code Changes:**

1. **Update Model Loading** (`backend/ml/predict.py`)

```python
class RetentionPredictor:
    def __init__(self, model_type='saas'):
        """
        Initialize predictor with model type.
        
        Args:
            model_type: 'saas' or 'telecom' (default: 'saas')
        """
        self.model_type = model_type
        self.base_path = Path(__file__).parent
        self.model_dir = self.base_path / 'models'
        
        # Load appropriate model
        if model_type == 'saas':
            self.model_data = self._load_saas_model()
        else:
            self.model_data = self._load_telecom_model()
        
        self.model = self.model_data['model']
        self.scaler = self.model_data['scaler']
        self.expected_features = self.model_data['feature_names']
    
    def _load_saas_model(self):
        """Load SaaS-specific model."""
        model_files = list(self.model_dir.glob('saas_churn_model_*.pkl'))
        if not model_files:
            raise FileNotFoundError("No SaaS model found")
        
        latest_model = max(model_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Loading SaaS model: {latest_model.name}")
        
        with open(latest_model, 'rb') as f:
            return pickle.load(f)
```

2. **Remove Feature Alignment** (No longer needed!)

```python
def prepare_features(self, df):
    """
    Prepare features for prediction (SaaS native).
    No feature alignment needed - model expects SaaS features.
    """
    logger.info("Preparing SaaS features for prediction...")
    
    # Drop customerID
    if 'customerID' in df.columns:
        df = df.drop('customerID', axis=1)
    
    # Drop Churn if present
    if 'Churn' in df.columns:
        df = df.drop('Churn', axis=1)
    
    # One-hot encode
    X = pd.get_dummies(df)
    
    # Align to expected features
    for feature in self.expected_features:
        if feature not in X.columns:
            X[feature] = 0
    
    # Reorder to match training
    X = X[self.expected_features]
    
    # Scale
    X_scaled = self.scaler.transform(X)
    
    return X_scaled, X.columns
```

3. **Update Prediction Service** (`backend/services/prediction_service.py`)

```python
# Initialize SaaS predictor (no longer Telecom)
predictor = RetentionPredictor(model_type='saas')
```

**Deployment Steps:**
1. Upload model file to S3 or include in Docker image
2. Update Docker image with new code
3. Deploy to ECS
4. Monitor metrics
5. A/B test if desired (compare Telecom vs SaaS model)

**Deliverables:**
- Updated code (3 files)
- Deployment scripts
- Rollback plan

---

#### **Subtask 1.7.4: Testing & Validation** (3 hours)

**Test Scenarios:**

1. **Functional Testing:**
   - ✅ Upload SaaS CSV → Prediction succeeds
   - ✅ Results returned with correct schema
   - ✅ No feature mismatch errors
   - ✅ Confidence scores reasonable

2. **Performance Testing:**
   - ✅ Prediction time < 2 seconds
   - ✅ Handle 1000-row CSV
   - ✅ No memory leaks

3. **Accuracy Testing:**
   - ✅ Compare predictions on holdout test set
   - ✅ Validate metrics (accuracy, precision, recall)
   - ✅ Ensure improvement over Telecom model

4. **Edge Cases:**
   - ✅ Missing optional features
   - ✅ Extreme values (very high MRR, very low usage)
   - ✅ New company (tenure = 1 month)

**Acceptance Criteria:**
- ✅ All tests pass
- ✅ Accuracy ≥ 85%
- ✅ No errors in logs
- ✅ Performance acceptable

**Deliverables:**
- Test results report
- Performance benchmarks
- Comparison: SaaS model vs Telecom model

---

#### **Subtask 1.7.5: Documentation & Cleanup** (2 hours)

**Documentation:**
1. Model card (metadata, performance, limitations)
2. Training notebook (reproducible)
3. Feature engineering guide
4. Deployment guide
5. User guide updates

**Code Cleanup:**
1. Remove feature alignment code (no longer needed)
2. Clean up Telecom-specific logic
3. Update comments and docstrings
4. Archive old Telecom model

**Deliverables:**
- Complete documentation
- Clean codebase
- Updated master plan

---

## 📊 **DATA GENERATION STRATEGY**

### **Synthetic Data Generation Script:**

```python
# scripts/generate_saas_training_data.py

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
np.random.seed(42)

def generate_saas_data(n_samples=10000):
    """
    Generate realistic SaaS churn dataset.
    """
    data = []
    
    for i in range(n_samples):
        # Basic info
        customer_id = f"SAAS_{i+1:06d}"
        tenure = np.random.choice([1, 3, 6, 12, 18, 24, 36], p=[0.15, 0.20, 0.20, 0.20, 0.10, 0.10, 0.05])
        
        # Company size affects MRR and seats
        company_size = np.random.choice(['Small', 'Medium', 'Large', 'Enterprise'], p=[0.40, 0.35, 0.20, 0.05])
        
        if company_size == 'Small':
            seats = np.random.randint(1, 10)
            mrr = np.random.uniform(29, 199)
        elif company_size == 'Medium':
            seats = np.random.randint(10, 50)
            mrr = np.random.uniform(199, 999)
        elif company_size == 'Large':
            seats = np.random.randint(50, 200)
            mrr = np.random.uniform(999, 4999)
        else:  # Enterprise
            seats = np.random.randint(200, 1000)
            mrr = np.random.uniform(4999, 19999)
        
        # Contract type
        contract = np.random.choice(['Month-to-month', 'Quarterly', 'Annual'], p=[0.30, 0.25, 0.45])
        
        # Usage patterns
        seats_used = max(1, int(seats * np.random.uniform(0.6, 1.0)))
        feature_usage = np.random.beta(5, 2) * 100  # Skewed toward high usage
        login_frequency = np.random.poisson(20)  # Average 20 logins/month
        api_calls = seats_used * np.random.randint(100, 1000)
        
        # Support & engagement
        support_tickets = np.random.poisson(tenure * 0.5)  # More tickets for longer tenure
        last_activity_days = np.random.exponential(3)  # Most active recently
        has_integration = np.random.choice([True, False], p=[0.70, 0.30])  # Most have integrations
        
        # Payment
        payment_method = np.random.choice(['Credit Card', 'Bank Transfer', 'Invoice'], p=[0.60, 0.25, 0.15])
        trial_converted = np.random.choice([True, False], p=[0.75, 0.25])
        
        # Industry
        industry = np.random.choice(['SaaS', 'Fintech', 'Healthcare', 'E-commerce', 'Education'], p=[0.30, 0.20, 0.15, 0.20, 0.15])
        
        # Total charges
        total_charges = mrr * tenure
        
        # Churn prediction (business logic)
        churn_risk = 0.05  # Base rate
        
        # Risk factors
        if contract == 'Month-to-month': churn_risk += 0.15
        if seats_used / seats < 0.7: churn_risk += 0.10  # Low utilization
        if feature_usage < 30: churn_risk += 0.15  # Low engagement
        if support_tickets > 5: churn_risk += 0.08  # High support needs
        if last_activity_days > 14: churn_risk += 0.12  # Inactive
        if not has_integration: churn_risk += 0.08  # No sticky integrations
        if not trial_converted: churn_risk += 0.05  # Didn't convert from trial
        if tenure < 3: churn_risk += 0.10  # Early stage risky
        
        # Protective factors
        if contract == 'Annual': churn_risk -= 0.20
        if seats_used / seats > 0.9: churn_risk -= 0.08  # High utilization
        if feature_usage > 70: churn_risk -= 0.10  # High engagement
        if has_integration: churn_risk -= 0.05  # Sticky
        if tenure > 12: churn_risk -= 0.08  # Established customer
        
        # Cap between 0 and 1
        churn_risk = max(0, min(1, churn_risk))
        
        # Random churn based on risk
        churned = 1 if np.random.random() < churn_risk else 0
        
        data.append({
            'customerID': customer_id,
            'tenure': tenure,
            'MonthlyCharges': round(mrr, 2),
            'TotalCharges': round(total_charges, 2),
            'Contract': contract,
            'company_size': company_size,
            'industry': industry,
            'feature_usage_score': round(feature_usage, 1),
            'support_tickets': support_tickets,
            'login_frequency': login_frequency,
            'api_calls_per_month': api_calls,
            'seats_purchased': seats,
            'seats_used': seats_used,
            'last_activity_days_ago': int(last_activity_days),
            'has_integration': has_integration,
            'payment_method': payment_method,
            'trial_converted': trial_converted,
            'Churn': churned
        })
    
    df = pd.DataFrame(data)
    
    # Print stats
    print(f"Generated {len(df)} samples")
    print(f"Churn rate: {df['Churn'].mean():.2%}")
    print(f"Average MRR: ${df['MonthlyCharges'].mean():.2f}")
    print(f"Average tenure: {df['tenure'].mean():.1f} months")
    
    return df

# Generate training data
df_train = generate_saas_data(10000)
df_train.to_csv('data/saas_training_data.csv', index=False)

# Generate test data
df_test = generate_saas_data(2000)
df_test.to_csv('data/saas_test_data.csv', index=False)

print("✅ Training and test data generated!")
```

---

## 📈 **EXPECTED OUTCOMES**

### **Technical:**
- ✅ Model accuracy: 85-90% (vs 76% current)
- ✅ Native SaaS features (no alignment needed)
- ✅ Faster predictions (no overhead)
- ✅ Better feature importance insights

### **Business:**
- ✅ Better predictions = higher customer value
- ✅ SaaS-specific insights actionable
- ✅ Marketing: "ML trained on SaaS data"
- ✅ Competitive differentiation

### **Product:**
- ✅ Clean architecture
- ✅ No workarounds
- ✅ Highway-grade quality
- ✅ Scalable for future models

---

## 🗓️ **TIMELINE**

### **Week 1:**
- Day 1-2: Data generation & preparation (6h)
- Day 3-4: Model training & evaluation (8h)

### **Week 2:**
- Day 1: Integration & deployment (4h)
- Day 2: Testing & validation (3h)
- Day 3: Documentation & cleanup (2h)

**Total: 23 hours over 2 weeks**

---

## 💰 **COST-BENEFIT ANALYSIS**

### **Investment:**
- Development time: 23 hours
- Testing time: 3 hours
- Total: ~3-4 days

### **Benefits:**
- **Accuracy:** +9-14 percentage points
- **Customer Value:** Better predictions = higher ROI
- **Marketing:** Credibility boost ("SaaS-trained model")
- **Maintenance:** Cleaner code, easier to improve
- **Scalability:** Foundation for future industry models

### **ROI:**
- Short-term: Improved accuracy → better customer retention
- Long-term: Competitive advantage, easier feature additions
- **Verdict:** HIGH ROI, worth the investment

---

## 🎯 **SUCCESS CRITERIA**

1. ✅ Model accuracy ≥ 85%
2. ✅ No feature mismatch errors
3. ✅ All tests pass
4. ✅ Performance < 2 seconds per prediction
5. ✅ Clean code, no workarounds
6. ✅ Documentation complete
7. ✅ Production deployment successful

---

## 📝 **DEPENDENCIES**

### **Prerequisites:**
- ✅ Task 1.5 complete (column mapper)
- ✅ Current temporary fix deployed (working system)
- ✅ Training data generated
- ✅ Model training environment ready

### **Blocks:**
- None (can start immediately)

---

## 🚀 **DEPLOYMENT STRATEGY**

### **Option 1: Direct Replacement (Recommended)**
- Replace Telecom model with SaaS model
- SaaS-only company → SaaS-only model
- Clean, simple, no confusion

### **Option 2: A/B Testing**
- Deploy both models
- Compare predictions side-by-side
- Validate improvement before full rollout
- More conservative

### **Recommendation: Option 1**
- We're SaaS-only, no need for A/B test
- Faster deployment
- Simpler architecture

---

## 📊 **METRICS TO TRACK**

### **Model Performance:**
- Accuracy, Precision, Recall, F1, AUC-ROC
- Feature importance rankings
- Prediction confidence distribution

### **Business Metrics:**
- Upload success rate
- Prediction completion rate
- User satisfaction (feedback)
- Trial conversion rate

### **Technical Metrics:**
- Prediction latency
- Error rate
- Model size
- Memory usage

---

## 🎓 **LEARNINGS & BEST PRACTICES**

### **Data Generation:**
- Use business logic for churn patterns
- Ensure realistic distributions
- Balance churn rate (~5-7% for B2B SaaS)
- Add noise for robustness

### **Model Training:**
- Use cross-validation
- Feature engineering important
- XGBoost works well for tabular data
- Save scaler with model

### **Deployment:**
- Version models (timestamp in filename)
- Include metadata (metrics, features)
- Comprehensive logging
- Rollback plan ready

---

**Status:** 📋 **READY TO IMPLEMENT**

**Next Steps:**
1. Review and approve plan
2. Generate training data
3. Train model
4. Deploy to production
5. Monitor and iterate

**This is the PERMANENT, LONG-TERM solution for SaaS churn prediction.**

