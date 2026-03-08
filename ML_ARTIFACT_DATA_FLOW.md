# Machine Learning Artifact Data Flow

## Quick Reference Guide

This document provides visual diagrams and quick lookups for the ML artifact interface.

---

## 1. DATA FLOW DIAGRAM

```
┌──────────────────────────────────────────────────────────────────┐
│                     TRAINING PIPELINE                             │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  PostgreSQL Database (Neon)  │
        │  cleaned_train_80_percent    │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   Sentiment_Analyzer         │
        │   + VADER sentiment          │
        │   + Text cleaning            │
        └──────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │   enriched_df (DataFrame)    │
        │   + sentiment_label          │
        │   + combined_sentiment       │
        │   + text_cleaned             │
        └──────────┬───────────────────┘
                   │
        ┌──────────┴───────────┬────────────────┬────────────────┐
        ▼                      ▼                ▼                ▼
┌───────────────┐    ┌─────────────────┐  ┌──────────┐  ┌──────────────┐
│Theme_Extractor│    │Risk_Score_Engine│  │Risk_Trends│  │Global_Themes │
│+ TF-IDF       │    │+ Sub-scores     │  │+ Monthly  │  │+ Theme counts│
│+ Themes       │    │+ Alert levels   │  │  trends   │  │              │
└───────┬───────┘    └────────┬────────┘  └─────┬────┘  └──────┬───────┘
        │                     │                  │               │
        └─────────┬───────────┴──────────────────┼───────────────┘
                  │                              │
                  ▼                              │
        ┌──────────────────────────────┐        │
        │  risk_results (dict)         │        │
        │  + risk_score per product    │        │
        │  + sub_scores                │        │
        │  + top_themes                │        │
        └──────────┬───────────────────┘        │
                   │                            │
                   ▼                            │
        ┌──────────────────────────────┐        │
        │  Revenue_Impact_Calculator   │        │
        │  + revenue_impact field      │        │
        └──────────┬───────────────────┘        │
                   │                            │
        ┌──────────┴───────────┬────────────────┤
        ▼                      ▼                ▼
┌───────────────┐    ┌─────────────────┐  ┌──────────────┐
│portfolio_     │    │alerts (list)    │  │risk_trends   │
│impact (dict)  │    │CRITICAL + HIGH  │  │global_themes │
└───────┬───────┘    └────────┬────────┘  └──────┬───────┘
        │                     │                   │
        └─────────────────────┴───────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────┐
        │         Risk_Model_Artifacts.pkl                │
        │  {                                              │
        │    enriched_df, risk_results, portfolio_impact, │
        │    alerts, risk_trends, global_themes,          │
        │    tfidf_vectorizer                             │
        │  }                                              │
        └──────────────────────┬──────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FLASK DASHBOARD BACKEND                       │
└──────────────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┬─────────────┬──────────────┐
        ▼              ▼              ▼             ▼              ▼
┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│Dashboard │  │Products   │  │Product   │  │Trends    │  │Chatbot   │
│KPI Cards │  │Table      │  │Detail    │  │Charts    │  │Assistant │
└──────────┘  └───────────┘  └──────────┘  └──────────┘  └──────────┘
      │              │              │            │              │
      └──────────────┴──────────────┴────────────┴──────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │  End Users    │
                            │  - Marketing  │
                            │  - Engineering│
                            │  - Finance    │
                            │  - Support    │
                            └───────────────┘
```

---

## 2. ARTIFACT KEY DEPENDENCY MAP

### Dashboard Endpoint → Artifact Keys

```
/api/dashboard
├─ risk_results ────────┐
├─ portfolio_impact     ├──→ KPI Summary
├─ alerts ──────────────┘
└─ enriched_df ─────────→ Total Reviews Count

/api/products
└─ risk_results ─────────→ Product List Table

/api/products/<asin>
├─ risk_results ─────────→ Product Risk Info
└─ enriched_df ──────────→ Sentiment Timeline, Rating Distribution, Recent Reviews

/api/trends
├─ risk_trends ──────────→ Sentiment Over Time Chart
└─ global_themes ────────→ Top Complaint Themes

/api/analyze (real-time)
├─ enriched_df ──────────→ Sentiment Analysis Template
└─ risk_results ─────────→ Current Product Risk Lookup

/api/chatbot
└─ risk_results ─────────→ Product Query Responses

/api/developer/dell-infrastructure-fit
├─ enriched_df ──────────→ Dataset Size Calculation
└─ risk_results ─────────→ Product Count Stats
```

---

## 3. ARTIFACT SIZE BREAKDOWN

Typical artifact file composition:

```
Risk_Model_Artifacts.pkl (Total: ~5-50 MB)
│
├─ enriched_df (80-95% of file size)
│  │  Full review dataset with sentiment columns
│  │  Size scales with: # reviews × # columns × data types
│  └─ Optimization: Use category dtypes for repeated strings
│
├─ risk_results (5-10%)
│  │  Dict with one entry per product
│  │  Size scales with: # products × theme count
│  └─ Typically 50-500 KB for 40 products
│
├─ portfolio_impact (<1%)
│  │  Single dict with ~7 aggregated values
│  └─ ~1 KB
│
├─ alerts (1-2%)
│  │  List of high-priority products
│  │  Size scales with: # CRITICAL/HIGH products
│  └─ Typically 5-20 KB
│
├─ risk_trends (1-2%)
│  │  List with one entry per month
│  │  Size scales with: # months in dataset
│  └─ Typically 1-5 KB for 2-3 years
│
├─ global_themes (<1%)
│  │  Dict mapping theme names to counts
│  └─ ~1 KB
│
└─ tfidf_vectorizer (2-5%)
   │  Sklearn TfidfVectorizer object with vocabulary
   │  Size scales with: vocabulary size (max_features parameter)
   └─ Typically 50-200 KB for 3000 features
```

---

## 4. ENRICHED_DF SCHEMA AT A GLANCE

```python
enriched_df: pandas.DataFrame
│
├─ FROM SOURCE DATA (database columns)
│  ├─ asin                  str          Product ID (grouping key)
│  ├─ text                  str          Original review text
│  ├─ title_x               str          Review title
│  ├─ rating                float        1-5 stars
│  ├─ date                  datetime64   Review date
│  ├─ helpful_vote          int/float    Community votes
│  ├─ average_rating        float        Product's overall rating
│  ├─ title_y               str          Product name
│  └─ price                 float        Product price (USD)
│
└─ ADDED BY TRAINING PIPELINE
   ├─ text_cleaned          str          HTML stripped, normalized
   ├─ text_sentiment        float        VADER body score (-1 to 1)
   ├─ title_sentiment       float        VADER title score (-1 to 1)
   ├─ combined_sentiment    float        Weighted average
   └─ sentiment_label       str          'positive'/'negative'/'neutral'
```

**Row Count:** Equals number of reviews in training data (typically 5,000-50,000)

**Memory Usage:** ~2-10 MB per 10,000 reviews

---

## 5. RISK_RESULTS SCHEMA AT A GLANCE

```python
risk_results: dict[str, dict]
{
  "B01ABC1234": {                        # ASIN as key
    # CORE FIELDS (always present)
    "asin": "B01ABC1234",                # str
    "product_name": "Dell Inspiron...",  # str (max 80 chars)
    "risk_score": 67.3,                  # float (0-100) or None
    "alert_level": "HIGH",               # str (5 levels)
    "review_count": 142,                 # int
    "average_rating": 3.8,               # float or None
    "price": 799.99,                     # float or None
    
    # SUB-SCORES (dict with 6 components)
    "sub_scores": {
      "negative_sentiment_ratio": 28.5,  # 0-100
      "sentiment_velocity": 15.2,        # 0-100
      "rating_decline": 22.8,            # 0-100
      "low_rating_spike": 12.0,          # 0-100
      "complaint_concentration": 18.5,   # 0-100
      "community_validated": 20.3,       # 0-100
    },
    
    # THEMES (list of tuples)
    "top_themes": [
      ("battery", 0.42),                 # 42% of neg reviews mention battery
      ("overheating", 0.35),
      ("screen", 0.28),
    ],
    
    # REVENUE IMPACT (dict with 5 fields)
    "revenue_impact": {
      "monthly_revenue_at_risk": 583000.00,
      "annualized_revenue_at_risk": 6996000.00,
      "potential_monthly_savings": 408100.00,
      "potential_annual_savings": 4897200.00,
      "risk_factor_percent": 10.05,
    },
  },
  # ... more products
}
```

**Entry Count:** One per product (typically 40-200)

**Memory Usage:** ~10-50 KB per product

---

## 6. ALERT LEVEL THRESHOLDS

Visual reference for risk score → alert level mapping:

```
  0 ──────────────── 24.9    LOW            ░░░░░░░░
 25 ──────────────── 49.9    MODERATE       ▒▒▒▒▒▒▒▒
 50 ──────────────── 74.9    HIGH           ▓▓▓▓▓▓▓▓
 75 ──────────────── 100     CRITICAL       ████████
  ?                          INSUFFICIENT   ????????
                             (< 3 reviews)
```

---

## 7. SUB-SCORE CONTRIBUTION

Default weighting in composite risk score:

```
Composite Risk Score (0-100) = Weighted Sum of:

negative_sentiment_ratio  ████████████████████████░  25%
rating_decline            ████████████████░░░░░░░░░  20%
sentiment_velocity        ███████████░░░░░░░░░░░░░░  15%
low_rating_spike          ███████████░░░░░░░░░░░░░░  15%
community_validated       ███████████░░░░░░░░░░░░░░  15%
complaint_concentration   ██████░░░░░░░░░░░░░░░░░░░  10%
```

---

## 8. REVENUE IMPACT CALCULATION

```
Product Monthly Revenue at Risk = 
    AVG_PRODUCT_MONTHLY_REVENUE × risk_factor

where:
    AVG_PRODUCT_MONTHLY_REVENUE = $5,833,333  (Company revenue / 40 products)
    risk_factor = (risk_score / 100) × 0.15   (Max 15% revenue impact)

Example:
    risk_score = 67.3
    risk_factor = (67.3 / 100) × 0.15 = 0.10095
    monthly_at_risk = $5,833,333 × 0.10095 = $588,742
    potential_savings = $588,742 × 0.70 = $412,119  (70% recovery rate)
```

---

## 9. DASHBOARD UI COMPONENT TRACE

Track which UI elements depend on which artifact keys:

### Dashboard.html Main KPIs

```
┌─────────────────────────────────────┐
│  PRODUCTS ANALYZED        [42]      │ ← risk_results (dict length)
│  CRITICAL ALERTS          [8]       │ ← risk_results (count alert_level="CRITICAL")
│  HIGH ALERTS              [15]      │ ← risk_results (count alert_level="HIGH")
│  REVENUE AT RISK          [$2.4M]   │ ← portfolio_impact['total_monthly_revenue_at_risk']
│  AVG RISK SCORE           [52.3]    │ ← risk_results (mean of risk_score)
│  TOTAL REVIEWS ANALYZED   [15,247]  │ ← enriched_df (row count)
└─────────────────────────────────────┘
```

### Product_Risk.html Product Table

```
┌──────────┬─────────────────┬────────┬────────────┬────────────────┐
│ ASIN     │ Product Name    │ Risk   │ Alert      │ Top Themes     │
├──────────┼─────────────────┼────────┼────────────┼────────────────┤
│ B01XYZ   │ Dell Inspiron...│  67.3  │ HIGH       │ battery, heat  │ ← risk_results
│          │                 │        │            │                │
│          │  ^              │   ^    │    ^       │       ^        │
│          │  |              │   |    │    |       │       |        │
│          │  product_name   │   |    │    |       │   top_themes   │
│          │                 │   |    │    |       │   (first 3)    │
│          │                 │   |    │    |       │                │
│          │            risk_score alert_level     │                │
└──────────┴─────────────────┴────────┴────────────┴────────────────┘
```

### Product Detail Sentiment Timeline

```
Sentiment Score
    1.0 │                          /\
        │                     /\  /  \
    0.5 │                /\  /  \/    \    ← enriched_df grouped by year_month
        │           /\  /  \/            \     .agg(avg_sentiment)
    0.0 ├───────/\──/──\/────────────────\────
        │      /  \/                       \
   -0.5 │     /                             \/\
        │                                       
   -1.0 │────┴────┴────┴────┴────┴────┴────┴───
         Jan  Feb  Mar  Apr  May  Jun  Jul  Aug
         2022 ────────────────────────────→ time
```

---

## 10. TRAINING PIPELINE EXECUTION TRACE

Step-by-step trace of `Train_Model.py`:

```
main()
│
├─ [Step 1] Connect to Database
│  └─ pd.read_sql("SELECT * FROM cleaned_train_80_percent")
│     └─ Returns: raw_df (DataFrame with ~15,000 reviews)
│
├─ [Step 2] Sentiment Analysis
│  └─ analyze_sentiment(raw_df)
│     ├─ clean_review_text() → text_cleaned
│     ├─ VADER on body → text_sentiment
│     ├─ VADER on title → title_sentiment
│     ├─ Weighted combine → combined_sentiment
│     └─ Classify → sentiment_label
│     └─ Returns: enriched_df (DataFrame + 5 new columns)
│
├─ [Step 3] TF-IDF Training
│  └─ train_tfidf_model(enriched_df)
│     └─ Filter negative reviews
│     └─ TfidfVectorizer(max_features=3000)
│     └─ Returns: tfidf_vectorizer, feature_names
│
├─ [Step 4] Risk Scoring
│  └─ compute_product_risk_scores(enriched_df)
│     ├─ Group by ASIN
│     ├─ For each product:
│     │  ├─ _negative_sentiment_ratio()
│     │  ├─ _sentiment_velocity()
│     │  ├─ _rating_decline()
│     │  ├─ _low_rating_spike()
│     │  ├─ _complaint_concentration()
│     │  ├─ _community_validated()
│     │  ├─ Weighted sum → risk_score
│     │  ├─ _get_alert_level(risk_score)
│     │  └─ extract_themes() → top_themes
│     └─ Returns: risk_results (dict)
│
├─ [Step 5] Revenue Impact
│  ├─ For each product in risk_results:
│  │  └─ calculate_revenue_impact(risk_score)
│  │     └─ Adds: revenue_impact field
│  └─ calculate_portfolio_impact(risk_results)
│     └─ Returns: portfolio_impact (dict)
│
├─ [Step 6] Aggregations
│  ├─ compute_risk_trends(enriched_df) → risk_trends (list)
│  ├─ get_global_theme_counts(enriched_df) → global_themes (dict)
│  └─ generate_alerts(risk_results) → alerts (list)
│
└─ [Step 7] Serialize Artifact
   └─ pickle.dump({
        enriched_df,
        risk_results,
        portfolio_impact,
        alerts,
        risk_trends,
        global_themes,
        tfidf_vectorizer
      }, Risk_Model_Artifacts.pkl)
```

**Execution Time:** ~30-90 seconds for 15,000 reviews

**Output File Size:** ~5-50 MB depending on review count

---

## 11. VALIDATION PIPELINE TRACE

Step-by-step trace of `Validate_Model.py`:

```
main()
│
├─ [Step 1] Load Training Artifacts
│  └─ pickle.load(Risk_Model_Artifacts.pkl)
│     └─ Extract: train_risk = artifacts['risk_results']
│
├─ [Step 2] Pull Test Data
│  └─ pd.read_sql("SELECT * FROM cleaned_test_20_percent")
│     └─ Returns: test_df (DataFrame with ~3,750 reviews)
│
├─ [Step 3] Analyze Test Data
│  └─ analyze_sentiment(test_df)
│     └─ Returns: test_enriched
│
├─ [Step 4] Score Test Period
│  └─ compute_product_risk_scores(test_enriched)
│     └─ Returns: test_risk (dict)
│
├─ [Step 5] Compare Train vs Test
│  ├─ Find common products with scores in both periods
│  ├─ Calculate:
│  │  ├─ Pearson correlation (train_scores, test_scores)
│  │  ├─ Directional accuracy (above/below median consistency)
│  │  ├─ High-risk recall (did we catch high-risk products?)
│  │  ├─ Score drift (avg test - avg train)
│  │  └─ Time-to-detection advantage (vs simple threshold)
│  └─ _revenue_replay() → Estimate revenue saved
│
└─ [Step 6] Save Validation Report
   └─ json.dump(report, Validation_Report.json)
```

**Execution Time:** ~20-60 seconds

**Output:** Validation_Report.json (~1 KB)

---

## 12. REAL-TIME PREDICTION FLOW

How `/api/analyze` processes a new review:

```
POST /api/analyze
{
  "text": "Battery dies after 2 hours",
  "title": "Terrible battery life",
  "rating": 2,
  "asin": "B01ABC1234"
}
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Build Single-Row DataFrame      │
│    pd.DataFrame([{...}])            │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 2. Run Sentiment Analysis           │
│    analyze_sentiment(review_df)     │
│    → combined_sentiment             │
│    → sentiment_label                │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 3. Extract Themes                   │
│    classify_review_themes(text)     │
│    → ["battery", "performance"]     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 4. Lookup Product Risk              │
│    artifacts['risk_results'][asin]  │
│    → current_product_risk_score     │
│    → product_alert_level            │
└──────────┬──────────────────────────┘
           │
           ▼
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

**Response Time:** ~50-200ms (in-memory operations only)

---

## 13. FILE SIZE OPTIMIZATION TIPS

### Reduce enriched_df Size

```python
# Before: enriched_df uses default dtypes (~10 MB for 10K reviews)
enriched_df['asin'] = enriched_df['asin'].astype('category')       # ✓ 75% reduction
enriched_df['sentiment_label'] = enriched_df['sentiment_label'].astype('category')  # ✓ 90% reduction
enriched_df['title_y'] = enriched_df['title_y'].astype('category')  # ✓ 60% reduction

# Drop intermediate columns if not needed
enriched_df = enriched_df.drop(columns=['text_sentiment', 'title_sentiment'])  # ✓ Save 2 columns

# After: ~4 MB for 10K reviews (60% reduction)
```

### Store Only Essential Columns

```python
# Dashboard only needs these columns from enriched_df:
essential_cols = [
    'asin', 'text', 'title_x', 'rating', 'date',
    'sentiment_label', 'combined_sentiment', 'text_cleaned',
    'helpful_vote', 'average_rating', 'title_y', 'price'
]
enriched_df = enriched_df[essential_cols]
```

### Compress Artifact File

```python
import gzip
import pickle

# Save compressed
with gzip.open("Risk_Model_Artifacts.pkl.gz", "wb") as f:
    pickle.dump(artifacts, f)

# Load compressed
with gzip.open("Risk_Model_Artifacts.pkl.gz", "rb") as f:
    artifacts = pickle.load(f)

# Typical compression: 50-70% size reduction
```

---

## 14. COMMON TROUBLESHOOTING

### Issue: Dashboard Shows "0 Products Analyzed"

**Root Cause:** `risk_results` is empty dict

**Check:**
```python
# In Train_Model.py output, look for:
print(f"Products scored: {scored} | Insufficient data: {insufficient}")

# If all products show "Insufficient data", check MIN_REVIEWS threshold
```

### Issue: Sentiment Timeline Not Displaying

**Root Cause:** `date` column not datetime type

**Fix:**
```python
# In Sentiment_Analyzer or Train_Model:
enriched_df['date'] = pd.to_datetime(enriched_df['date'], errors='coerce')
```

### Issue: Real-Time Analysis Returns "Product Not Found"

**Root Cause:** ASIN in request doesn't exist in `risk_results`

**Check:**
```python
# After loading artifacts:
print(list(artifacts['risk_results'].keys())[:10])  # Show first 10 ASINs
```

### Issue: Pickle Load Error

**Root Cause:** Artifact contains unpicklable object (e.g., database connection)

**Fix:**
```python
# Never include these in artifacts:
# ❌ Database connections
# ❌ Open file handles
# ❌ Threading locks
# ❌ Lambda functions defined outside module

# ✓ Only primitive types, DataFrames, dicts, lists, sklearn models
```

---

## 15. QUICK COMMAND REFERENCE

### Train Model
```bash
cd src
python Train_Model.py
```

### Validate Model
```bash
cd src
python Validate_Model.py
```

### Start Dashboard
```bash
cd src
python Run_System.py
# or
python Flask_API.py
```

### Inspect Artifact
```python
import pickle
with open("src/models/Risk_Model_Artifacts.pkl", "rb") as f:
    artifacts = pickle.load(f)

print("Keys:", artifacts.keys())
print("Products:", len(artifacts['risk_results']))
print("Reviews:", len(artifacts['enriched_df']))
print("Alerts:", len(artifacts['alerts']))
```

### Check Artifact Size
```bash
# Windows PowerShell
Get-Item "src\models\Risk_Model_Artifacts.pkl" | Select-Object Name, Length

# Linux/Mac
ls -lh src/models/Risk_Model_Artifacts.pkl
```

---

**End of Data Flow Guide**

*For detailed interface specification, see: ML_ARTIFACT_INTERFACE_SPECIFICATION.md*
