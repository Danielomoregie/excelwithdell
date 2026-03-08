# Machine Learning Artifact Interface Specification

## Document Purpose

This specification defines the **interface contract** between the training pipeline and the dashboard backend for the FusionTech Product Risk Management System. Any ML algorithm can be substituted for the current implementation as long as it produces an artifact file that conforms to this specification.

**Version:** 1.0  
**Last Updated:** 2026-03-07  
**Artifact File:** `src/models/Risk_Model_Artifacts.pkl`

---

## 1. ARTIFACT LOADING MECHANISM

### 1.1 File Location and Format

- **Path:** `src/models/Risk_Model_Artifacts.pkl`
- **Format:** Python pickle file (protocol 5 recommended)
- **Load Method:** `pickle.load()`

### 1.2 Loading Code

The artifact is loaded once at Flask server startup:

```python
# src/Flask_API.py, lines 87-97
def load_artifacts():
    global artifacts
    if not os.path.exists(ARTIFACTS_PATH):
        raise FileNotFoundError(
            f"Model artifacts not found at {ARTIFACTS_PATH}. Run Train_Model.py first."
        )
    with open(ARTIFACTS_PATH, "rb") as f:
        artifacts = pickle.load(f)
    print(f"Loaded model artifacts ({len(artifacts['risk_results'])} products)")
```

The `artifacts` object is stored as a **global variable** and accessed by all Flask routes.

---

## 2. ARTIFACT STRUCTURE

The artifact **MUST** be a Python dictionary with the following keys:

```python
artifacts = {
    "enriched_df": pandas.DataFrame,          # REQUIRED
    "risk_results": dict,                     # REQUIRED
    "portfolio_impact": dict,                 # REQUIRED
    "alerts": list,                           # REQUIRED
    "risk_trends": list,                      # REQUIRED
    "global_themes": dict,                    # REQUIRED
    "tfidf_vectorizer": object or None,       # OPTIONAL
}
```

### 2.1 Key: `enriched_df`

**Type:** `pandas.DataFrame`

**Purpose:** Full dataset of reviews with sentiment analysis and derived features.

**Required Columns:**

| Column | Type | Description | Usage |
|--------|------|-------------|-------|
| `asin` | str | Amazon Standard Identification Number (product ID) | Product grouping and filtering |
| `text` | str | Original review text | Real-time analysis, fallback display |
| `title_x` | str | Review title | Display in product detail views |
| `rating` | float | Star rating (1-5) | Sentiment timeline, rating distribution |
| `date` | datetime64 | Review submission date | Temporal analysis, trend charts |
| `sentiment_label` | str | One of: 'positive', 'negative', 'neutral' | Filtering negative reviews |
| `combined_sentiment` | float | Sentiment score (-1.0 to +1.0) | Timeline charts, trend analysis |
| `text_cleaned` | str | Cleaned review text (no HTML, normalized whitespace) | Theme extraction, text analysis |
| `helpful_vote` | int/float | Number of helpful votes | Community validation scoring |
| `average_rating` | float | Product's overall average rating | Rating decline calculations |
| `title_y` | str | Product name/title | Display in UI, chatbot responses |
| `price` | float (nullable) | Product price in USD | Revenue impact adjustments |

**Optional Columns (if present, may be used):**
- `text_sentiment`: float (-1.0 to +1.0) - Sentiment of review body
- `title_sentiment`: float (-1.0 to +1.0) - Sentiment of review title
- `year_month`: pandas.Period - Cached period for grouping

**Dashboard Usage:**
- `/api/dashboard`: Count total reviews analyzed
- `/api/products/<asin>`: Extract product-specific reviews for sentiment timeline, rating distribution, recent negative reviews
- `/api/analyze`: Template for real-time review analysis

**Code References:**
- Created by: `Sentiment_Analyzer.analyze_sentiment()` (line 33-73)
- Used in: `Flask_API.py` lines 898, 952, 958, 1176

---

### 2.2 Key: `risk_results`

**Type:** `dict[str, dict]`

**Purpose:** Per-product risk scores, sub-scores, themes, and metadata.

**Structure:**

```python
risk_results = {
    "B01ABC1234": {  # ASIN as key
        # REQUIRED FIELDS
        "asin": str,              # Product ASIN (matches key)
        "product_name": str,      # Display name (truncated to 80 chars)
        "risk_score": float or None,  # 0-100 composite risk score, None if insufficient data
        "alert_level": str,       # One of: "CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT DATA"
        "review_count": int,      # Number of reviews for this product
        
        # REQUIRED SCORING DETAILS
        "sub_scores": {
            "negative_sentiment_ratio": float,    # 0-100
            "sentiment_velocity": float,          # 0-100
            "rating_decline": float,              # 0-100
            "low_rating_spike": float,            # 0-100
            "complaint_concentration": float,     # 0-100
            "community_validated": float,         # 0-100
        },
        
        # REQUIRED THEMES
        "top_themes": [
            ("theme_name", frequency_ratio),  # e.g., ("battery", 0.42)
            # List of tuples, sorted by frequency descending
            # frequency_ratio is fraction of negative reviews mentioning this theme
        ],
        
        # REQUIRED METADATA
        "average_rating": float or None,  # Product's overall star rating
        "price": float or None,           # Product price in USD
        
        # REQUIRED REVENUE IMPACT (added by training pipeline)
        "revenue_impact": {
            "monthly_revenue_at_risk": float,
            "annualized_revenue_at_risk": float,
            "potential_monthly_savings": float,
            "potential_annual_savings": float,
            "risk_factor_percent": float,
        },
    },
    # ... more products
}
```

**Alert Level Mapping:**

```python
def _get_alert_level(risk_score):
    if risk_score >= 75:
        return "CRITICAL"
    elif risk_score >= 50:
        return "HIGH"
    elif risk_score >= 25:
        return "MODERATE"
    else:
        return "LOW"
```

**Dashboard Usage:**
- `/api/dashboard`: Count total products, scored products, critical/high alerts, average risk score
- `/api/products`: List all products with risk data
- `/api/products/<asin>`: Product detail view
- `/api/analyze`: Lookup current product risk for new review
- `/api/chatbot`: Product-specific risk summaries

**Code References:**
- Created by: `Risk_Score_Engine.compute_product_risk_scores()` (line 155-213)
- Revenue impact added by: `Revenue_Impact_Calculator.calculate_revenue_impact()` (line 18-50)
- Used in: `Flask_API.py` lines 887, 923, 951, 1060, 1083

---

### 2.3 Key: `portfolio_impact`

**Type:** `dict`

**Purpose:** Aggregate revenue impact across all scored products.

**Structure:**

```python
portfolio_impact = {
    "total_monthly_revenue_at_risk": float,        # Sum across all products
    "total_annual_revenue_at_risk": float,         # monthly * 12
    "total_potential_monthly_savings": float,      # Recoverable with prompt action
    "total_potential_annual_savings": float,       # savings * 12
    "products_at_risk": int,                       # Count of products with risk > 0
    "company_monthly_revenue": float,              # Total company revenue baseline
    "percent_portfolio_at_risk": float,            # % of company revenue at risk
}
```

**Dashboard Usage:**
- `/api/dashboard`: Display total monthly revenue at risk in KPI card

**Code References:**
- Created by: `Revenue_Impact_Calculator.calculate_portfolio_impact()` (line 54-81)
- Used in: `Flask_API.py` line 888

---

### 2.4 Key: `alerts`

**Type:** `list[dict]`

**Purpose:** Filtered list of high-priority products requiring immediate attention.

**Structure:**

```python
alerts = [
    {
        "asin": str,
        "product_name": str,
        "risk_score": float,
        "alert_level": str,           # "CRITICAL" or "HIGH"
        "top_themes": [str, str, ...],  # List of theme names (not tuples)
        "review_count": int,
    },
    # ... sorted by risk_score descending
]
```

**Filtering Rule:** Only products with `alert_level` in `["CRITICAL", "HIGH"]` are included.

**Dashboard Usage:**
- `/api/dashboard`: Display top 10 alerts in alert panel

**Code References:**
- Created by: `Risk_Score_Engine.generate_alerts()` (line 234-251)
- Used in: `Flask_API.py` line 889, 917

---

### 2.5 Key: `risk_trends`

**Type:** `list[dict]`

**Purpose:** Monthly aggregated sentiment and rating trends across all products.

**Structure:**

```python
risk_trends = [
    {
        "month": str,              # Format: "2022-01" (pandas Period string)
        "avg_sentiment": float,    # Mean combined_sentiment for month
        "negative_ratio": float,   # Fraction of reviews that are negative (0-1)
        "review_count": int,       # Total reviews in that month
        "avg_rating": float,       # Mean star rating for month
    },
    # ... sorted by month ascending
]
```

**Dashboard Usage:**
- `/api/trends`: Sentiment over time chart

**Code References:**
- Created by: `Risk_Score_Engine.compute_risk_trends()` (line 216-232)
- Used in: `Flask_API.py` line 1022

---

### 2.6 Key: `global_themes`

**Type:** `dict[str, int]`

**Purpose:** Global count of complaint themes across all negative reviews.

**Structure:**

```python
global_themes = {
    "battery": 142,
    "overheating": 98,
    "screen": 87,
    # ... sorted by count descending
}
```

**Dashboard Usage:**
- `/api/trends`: Display top global complaint themes

**Code References:**
- Created by: `Theme_Extractor.get_global_theme_counts()` (line 128-140)
- Used in: `Flask_API.py` line 1023

---

### 2.7 Key: `tfidf_vectorizer`

**Type:** `sklearn.feature_extraction.text.TfidfVectorizer` or `None`

**Purpose:** Trained TF-IDF model for extracting top complaint terms from negative reviews.

**Required Methods (if not None):**
- `transform(texts)`: Transform text to TF-IDF matrix
- `get_feature_names_out()`: Get vocabulary terms

**Dashboard Usage:**
- Currently used only during training for theme extraction
- Can be used for real-time term extraction in future

**Code References:**
- Created by: `Theme_Extractor.train_tfidf_model()` (line 90-110)
- Stored but not currently used in production dashboard

---

## 3. DASHBOARD ENDPOINT MAPPING

### 3.1 API Routes Using Artifacts

| Route | Artifact Keys Used | Purpose |
|-------|-------------------|---------|
| `/api/dashboard` | `risk_results`, `portfolio_impact`, `alerts`, `enriched_df` | Main KPI summary |
| `/api/products` | `risk_results` | Product table view |
| `/api/products/<asin>` | `risk_results`, `enriched_df` | Product detail page |
| `/api/trends` | `risk_trends`, `global_themes` | Trend charts |
| `/api/analyze` | `enriched_df`, `risk_results` | Real-time review analysis |
| `/api/chatbot` | `risk_results` | AI assistant product queries |
| `/api/developer/dell-infrastructure-fit` | `enriched_df`, `risk_results` | Enterprise infrastructure sizing |

### 3.2 Template Pages Using API Data

| Page | API Route | Artifact Dependency Chain |
|------|-----------|---------------------------|
| `Dashboard.html` | `/api/dashboard` | → `risk_results`, `portfolio_impact`, `alerts` |
| `Product_Risk.html` | `/api/products`, `/api/products/<asin>` | → `risk_results`, `enriched_df` |
| `raw_dataset.html` | `/api/raw-dataset/*` | → Database (not artifacts) |
| `dell_infrastructure_fit.html` | `/api/developer/dell-infrastructure-fit` | → `enriched_df`, `risk_results` |

---

## 4. TRAINING PIPELINE EXPECTATIONS

### 4.1 Input Data Requirements

The training algorithm **MUST** have access to the following data:

**Required Input Columns from Database:**

```python
training_data = pd.read_sql(
    "SELECT * FROM cleaned_train_80_percent ORDER BY date ASC",
    connection
)
```

**Expected Columns:**
- `asin`: str - Product identifier
- `text`: str - Review text
- `title_x`: str - Review title
- `rating`: float - Star rating (1-5)
- `date`: datetime - Review date
- `helpful_vote`: int/float - Helpful votes count
- `average_rating`: float - Product's overall rating
- `title_y`: str - Product name
- `price`: float (nullable) - Product price

### 4.2 Processing Pipeline Steps

The training algorithm **SHOULD** follow this sequence (or produce equivalent outputs):

1. **Sentiment Analysis:**
   - Clean review text (remove HTML, normalize whitespace)
   - Score sentiment for body and title
   - Combine scores (weighted: 70% body, 30% title)
   - Classify as 'positive', 'negative', or 'neutral'
   - Add columns: `text_cleaned`, `combined_sentiment`, `sentiment_label`

2. **Theme Extraction:**
   - On negative reviews, detect complaint themes
   - Categories: overheating, battery, screen, performance, keyboard, build_quality, software, connectivity, customer_service, value
   - Calculate theme frequency per product

3. **Risk Scoring:**
   - For each product (grouped by ASIN):
     - Calculate 6 sub-scores (0-100 each):
       - `negative_sentiment_ratio`: % negative reviews
       - `sentiment_velocity`: Sentiment worsening over time
       - `rating_decline`: Recent rating drop vs. overall
       - `low_rating_spike`: Surge in 1-2 star reviews
       - `complaint_concentration`: Single theme dominance
       - `community_validated`: Negative reviews with high helpful votes
     - Compute weighted composite (see weights in section 4.3)
     - Map score to alert level
     - Minimum 3 reviews required for scoring

4. **Revenue Impact:**
   - For each risk score, calculate revenue impact using:
     - Base monthly revenue: $5.83M per product
     - Risk factor: `(risk_score / 100) * 0.15` (max 15% impact)
     - Recovery rate: 70%

5. **Aggregation:**
   - Generate portfolio-level revenue sums
   - Filter alerts (CRITICAL + HIGH only)
   - Compute monthly trends
   - Count global themes

### 4.3 Scoring Weights

The composite risk score **SHOULD** use these weights (or document alternatives):

```python
WEIGHTS = {
    "negative_sentiment_ratio": 0.25,
    "sentiment_velocity": 0.15,
    "rating_decline": 0.20,
    "low_rating_spike": 0.15,
    "complaint_concentration": 0.10,
    "community_validated": 0.15,
}

risk_score = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
risk_score = round(min(max(risk_score, 0), 100), 1)
```

### 4.4 Artifact Serialization

The training script **MUST** save the artifact as:

```python
import pickle
import os

artifacts = {
    "enriched_df": enriched_df,
    "tfidf_vectorizer": tfidf_vectorizer,
    "risk_results": risk_results,
    "risk_trends": risk_trends,
    "global_themes": global_themes,
    "alerts": alerts,
    "portfolio_impact": portfolio_impact,
}

os.makedirs("src/models", exist_ok=True)
with open("src/models/Risk_Model_Artifacts.pkl", "wb") as f:
    pickle.dump(artifacts, f)
```

---

## 5. VALIDATION INTERFACE

### 5.1 Validation Data

The validation script (`Validate_Model.py`) expects:

- **Trained Artifacts:** `Risk_Model_Artifacts.pkl` with `risk_results` key
- **Test Data:** Table `cleaned_test_20_percent` in database
- **Validation Output:** `Risk_Model_Validation.json` report

### 5.2 Validation Metrics

The validation pipeline computes:

1. **Pearson Correlation:** Train risk scores vs. test risk scores for common products
2. **Directional Accuracy:** Did high-risk products stay high-risk?
3. **High-Risk Recall:** Of test-period high-risk products, what % were flagged in training?
4. **Score Drift:** Average score difference between train and test periods
5. **Time-to-Detection Advantage:** Months earlier detection vs. simple threshold

### 5.3 Validation Report Schema

```json
{
  "products_compared": 15,
  "pearson_correlation": 0.7842,
  "directional_accuracy": 0.8667,
  "high_risk_recall": 0.9000,
  "test_high_risk_count": 10,
  "avg_train_risk_score": 45.3,
  "avg_test_risk_score": 47.8,
  "score_drift": 2.5,
  "time_advantage_months": 3
}
```

---

## 6. INTERFACE CONTRACT SUMMARY

### 6.1 MANDATORY Requirements

An alternative training algorithm **MUST** produce:

✅ **File:** `src/models/Risk_Model_Artifacts.pkl`  
✅ **Format:** Python pickle dictionary  
✅ **Keys:** `enriched_df`, `risk_results`, `portfolio_impact`, `alerts`, `risk_trends`, `global_themes`

✅ **enriched_df Columns:**
- `asin`, `text`, `title_x`, `rating`, `date`, `sentiment_label`, `combined_sentiment`, `text_cleaned`, `helpful_vote`, `average_rating`, `title_y`, `price`

✅ **risk_results Structure:**
- Dictionary keyed by ASIN
- Required fields: `asin`, `product_name`, `risk_score`, `alert_level`, `review_count`, `sub_scores`, `top_themes`, `average_rating`, `price`, `revenue_impact`

✅ **portfolio_impact Structure:**
- Required fields: `total_monthly_revenue_at_risk`, `total_annual_revenue_at_risk`, `total_potential_monthly_savings`, `total_potential_annual_savings`, `products_at_risk`, `company_monthly_revenue`, `percent_portfolio_at_risk`

✅ **alerts Structure:**
- List of dicts with: `asin`, `product_name`, `risk_score`, `alert_level`, `top_themes`, `review_count`

✅ **risk_trends Structure:**
- List of dicts with: `month`, `avg_sentiment`, `negative_ratio`, `review_count`, `avg_rating`

✅ **global_themes Structure:**
- Dictionary mapping theme names to counts

### 6.2 OPTIONAL Enhancements

The following are **NOT** required for dashboard compatibility:

🔲 `tfidf_vectorizer`: Can be `None` if not used
🔲 Custom sub-score names in `risk_results['sub_scores']`: Dashboard displays whatever is present
🔲 Additional DataFrame columns in `enriched_df`: Dashboard uses only specified columns
🔲 Additional fields in `risk_results`: Dashboard ignores unknown fields
🔲 Custom theme categories: Any string theme names are supported

### 6.3 Breaking Changes

The following changes **WILL BREAK** the dashboard:

❌ Missing required artifact keys  
❌ Wrong data types (e.g., list instead of dict)  
❌ Missing required DataFrame columns  
❌ Missing required fields in `risk_results` dictionaries  
❌ `risk_score` outside 0-100 range or not float/None  
❌ `alert_level` not in `["CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT DATA"]`  
❌ Non-serializable objects in artifact (e.g., database connections)

---

## 7. REAL-TIME PREDICTION INTERFACE

### 7.1 New Review Analysis

The `/api/analyze` endpoint accepts a new review and returns:

```python
POST /api/analyze
{
    "text": "Battery dies after 2 hours...",
    "title": "Terrible battery life",
    "rating": 2,
    "asin": "B01ABC1234"
}

→ Response:
{
    "status": "success",
    "analysis": {
        "sentiment_score": -0.7234,
        "sentiment_label": "negative",
        "detected_themes": ["battery", "performance"],
        "current_product_risk_score": 67.3,
        "product_alert_level": "HIGH"
    }
}
```

**Implementation:** Uses `Sentiment_Analyzer.analyze_sentiment()` and `Theme_Extractor.classify_review_themes()` on single-row DataFrame, then looks up product risk from `artifacts['risk_results']`.

### 7.2 Batch Prediction

For batch scoring of new products or re-scoring existing products:

1. Load new reviews from database
2. Run sentiment analysis
3. Run theme extraction
4. Compute risk scores
5. Serialize updated artifact
6. Restart Flask server (or implement hot reload)

**Note:** The current system does **NOT** support real-time model updates without server restart.

---

## 8. NIGHTLY UPDATE WORKFLOW

### 8.1 Production Deployment Pattern

In a production environment, the typical workflow is:

```
┌─────────────────┐
│  CRON JOB / CI  │ Nightly at 2:00 AM
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  1. Run Train_Model.py          │
│     - Pull latest data from DB  │
│     - Compute risk scores       │
│     - Save artifacts            │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  2. Run Validate_Model.py       │
│     - Validate against holdout  │
│     - Save validation report    │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  3. Restart Flask Server        │
│     - Reload artifacts          │
│     - Dashboard shows new data  │
└─────────────────────────────────┘
```

### 8.2 Artifact Versioning

For production systems, consider:

- Save artifacts with timestamp: `Risk_Model_Artifacts_2026-03-07.pkl`
- Keep last N versions for rollback
- Log artifact file size and record count
- Track drift metrics over time

---

## 9. REPLACING THE TRAINING ALGORITHM

### 9.1 Step-by-Step Guide

To implement a completely different ML algorithm while maintaining dashboard compatibility:

**Step 1:** Understand Current Baseline
- Read `src/Train_Model.py` to see the full pipeline
- Note the column transformations and feature engineering

**Step 2:** Implement Your Algorithm
- Use any ML framework (scikit-learn, PyTorch, TensorFlow, etc.)
- Process input data to predict risk scores (0-100) per product
- Ensure minimum review threshold (recommend 3+)

**Step 3:** Map Outputs to Interface
- Convert your model's outputs to match `risk_results` schema
- Populate `sub_scores` with your model's feature importances or intermediate scores
- Extract themes using keyword matching or LLM-based classification

**Step 4:** Generate Supporting Artifacts
- Process full dataset to create `enriched_df`
- Aggregate to create `portfolio_impact`, `alerts`, `risk_trends`, `global_themes`
- Set `tfidf_vectorizer = None` if not used

**Step 5:** Serialize and Validate
- Save as `Risk_Model_Artifacts.pkl`
- Run `Validate_Model.py` to check compatibility
- Start Flask server and verify dashboard loads

**Step 6:** Test Endpoints
- Hit all API routes and verify responses
- Check dashboard UI for visual correctness
- Test real-time analysis with `/api/analyze`

### 9.2 Example: Deep Learning Replacement

```python
import torch
import pickle
import pandas as pd

# Hypothetical: Load your trained PyTorch model
model = torch.load("my_risk_model.pt")

# Load data
df = pd.read_sql("SELECT * FROM cleaned_train_80_percent", conn)

# Run inference
predictions = model.predict(df)  # Returns risk scores per product

# Build risk_results dictionary
risk_results = {}
for asin, group in df.groupby('asin'):
    score = predictions[predictions['asin'] == asin]['risk_score'].mean()
    
    risk_results[asin] = {
        "asin": asin,
        "product_name": group['title_y'].iloc[0],
        "risk_score": float(score),
        "alert_level": get_alert_level(score),
        "review_count": len(group),
        "sub_scores": {
            "model_confidence": float(predictions[predictions['asin'] == asin]['confidence'].mean()),
            # Add other interpretable scores
        },
        "top_themes": extract_themes_with_llm(group['text']),  # Custom function
        "average_rating": float(group['average_rating'].iloc[0]),
        "price": float(group['price'].iloc[0]) if 'price' in group.columns else None,
        "revenue_impact": calculate_revenue_impact(score),
    }

# Build full artifact
artifacts = {
    "enriched_df": df,  # With sentiment columns added
    "risk_results": risk_results,
    "portfolio_impact": calculate_portfolio_impact(risk_results),
    "alerts": generate_alerts(risk_results),
    "risk_trends": compute_risk_trends(df),
    "global_themes": extract_global_themes(df),
    "tfidf_vectorizer": None,
}

# Save
with open("src/models/Risk_Model_Artifacts.pkl", "wb") as f:
    pickle.dump(artifacts, f)
```

---

## 10. TESTING CHECKLIST

Before deploying a new training algorithm, verify:

### 10.1 Artifact Structure

- [ ] File exists at `src/models/Risk_Model_Artifacts.pkl`
- [ ] File can be loaded with `pickle.load()`
- [ ] All 7 required keys present in dictionary
- [ ] No unpicklable objects (database connections, file handles, etc.)

### 10.2 Data Types

- [ ] `enriched_df` is `pandas.DataFrame` with required columns
- [ ] `risk_results` is `dict` with string keys (ASINs)
- [ ] `portfolio_impact` is `dict` with required numeric fields
- [ ] `alerts` is `list` of dicts
- [ ] `risk_trends` is `list` of dicts
- [ ] `global_themes` is `dict` with string keys and int values

### 10.3 Value Ranges

- [ ] `risk_score` is float between 0-100 or None
- [ ] `alert_level` is one of 5 valid strings
- [ ] `combined_sentiment` is float between -1.0 and 1.0
- [ ] `sentiment_label` is 'positive', 'negative', or 'neutral'
- [ ] All financial values are non-negative

### 10.4 Dashboard Functionality

- [ ] Dashboard loads without errors
- [ ] KPI cards show correct values
- [ ] Product table displays all products
- [ ] Product detail page works for sample ASIN
- [ ] Trend charts render
- [ ] Alerts panel shows high-priority products
- [ ] Real-time analysis endpoint returns valid response
- [ ] Chatbot returns product summaries

### 10.5 Performance

- [ ] Artifact file size < 100 MB (recommend < 50 MB)
- [ ] Flask server startup < 10 seconds
- [ ] API responses < 1 second for typical queries

---

## 11. APPENDIX: CODE REFERENCES

### 11.1 Training Pipeline Files

| File | Purpose | Lines |
|------|---------|-------|
| `Train_Model.py` | Main training orchestration | 1-150 |
| `Sentiment_Analyzer.py` | VADER sentiment analysis | 1-100 |
| `Theme_Extractor.py` | Keyword-based theme extraction | 1-200 |
| `Risk_Score_Engine.py` | Risk score calculation | 1-320 |
| `Revenue_Impact_Calculator.py` | Financial impact estimates | 1-100 |

### 11.2 Dashboard Backend Files

| File | Purpose | Lines |
|------|---------|-------|
| `Flask_API.py` | API routes and artifact loading | 1-1500 |
| `Validate_Model.py` | Validation metrics | 1-200 |
| `Run_System.py` | System orchestration | 1-100 |

### 11.3 Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `load_artifacts()` | Flask_API.py:87 | Load pickle file into global variable |
| `analyze_sentiment()` | Sentiment_Analyzer.py:33 | Add sentiment columns to DataFrame |
| `compute_product_risk_scores()` | Risk_Score_Engine.py:155 | Calculate risk for all products |
| `calculate_revenue_impact()` | Revenue_Impact_Calculator.py:18 | Convert risk to revenue |
| `generate_alerts()` | Risk_Score_Engine.py:234 | Filter high-priority products |

---

## 12. CONTACT AND SUPPORT

For questions about this interface specification:

- **Training Pipeline Issues:** Review `Train_Model.py` source code
- **Dashboard Issues:** Review `Flask_API.py` routes
- **Data Schema Issues:** Check database table definitions in `Dataset_Scripts/Hosted_SQL_Scripts/`

---

**End of Specification**

*This document defines the interface contract version 1.0. Breaking changes to this interface should trigger a major version increment and require dashboard code updates.*
