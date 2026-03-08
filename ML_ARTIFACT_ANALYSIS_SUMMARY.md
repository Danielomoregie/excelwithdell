# ML Artifact Analysis - Executive Summary

**Date:** March 7, 2026  
**Repository:** FusionTech Product Risk Management System  
**Artifact File:** `src/models/Risk_Model_Artifacts.pkl`

---

## Analysis Objective

Produce a detailed specification of how the machine learning artifact (Risk_Model_Artifacts.pkl) is used by the system, enabling another developer to implement a completely different training algorithm while maintaining dashboard compatibility.

---

## Key Findings

### 1. Artifact Loading and Usage

**Location:** The artifact is loaded **once** at Flask server startup in `Flask_API.py` (lines 87-97) and stored as a **global variable** accessible to all routes.

```python
def load_artifacts():
    global artifacts
    with open(ARTIFACTS_PATH, "rb") as f:
        artifacts = pickle.load(f)
```

**No hot reload:** Changes to the artifact require a server restart.

### 2. Artifact Structure

The artifact is a Python dictionary with **7 keys**, of which **6 are mandatory**:

| Key | Type | Required | Purpose |
|-----|------|----------|---------|
| `enriched_df` | DataFrame | ✅ Yes | Full review dataset with sentiment analysis |
| `risk_results` | dict | ✅ Yes | Per-product risk scores and metadata |
| `portfolio_impact` | dict | ✅ Yes | Aggregate revenue impact |
| `alerts` | list | ✅ Yes | CRITICAL + HIGH priority products |
| `risk_trends` | list | ✅ Yes | Monthly sentiment trends |
| `global_themes` | dict | ✅ Yes | Global complaint theme counts |
| `tfidf_vectorizer` | object | ⚪ Optional | Sklearn TF-IDF model (not used in dashboard) |

### 3. Dashboard Dependency Map

**8 API endpoints** consume artifact data:

1. `/api/dashboard` → Uses: risk_results, portfolio_impact, alerts, enriched_df
2. `/api/products` → Uses: risk_results
3. `/api/products/<asin>` → Uses: risk_results, enriched_df
4. `/api/trends` → Uses: risk_trends, global_themes
5. `/api/analyze` → Uses: enriched_df, risk_results
6. `/api/chatbot` → Uses: risk_results
7. `/api/developer/dell-infrastructure-fit` → Uses: enriched_df, risk_results
8. `/api/raw-dataset/*` → Uses: Database directly (NOT artifacts)

**4 UI pages** depend on these endpoints:

- `Dashboard.html` → KPI cards, alerts panel
- `Product_Risk.html` → Product table, product detail views
- `dell_infrastructure_fit.html` → Enterprise infrastructure sizing
- `raw_dataset.html` → Database browser (no artifact dependency)

### 4. Critical Data Contracts

#### enriched_df (DataFrame)
- **Required columns:** 12 columns including `asin`, `text`, `rating`, `date`, `sentiment_label`, `combined_sentiment`, `text_cleaned`, etc.
- **Usage:** 
  - Count total reviews (dashboard KPI)
  - Extract product-specific reviews for timelines and distributions
  - Template for real-time review analysis
  - Enterprise infrastructure sizing calculations

#### risk_results (dict)
- **Structure:** Dictionary keyed by ASIN, each value is a product dict
- **Required fields per product:** 10 fields including `risk_score` (0-100 or None), `alert_level`, `sub_scores` (6 components), `top_themes`, `revenue_impact`
- **Usage:**
  - Dashboard KPIs (total products, scored products, average risk, critical/high counts)
  - Product table rendering
  - Product detail pages
  - Chatbot product queries
  - Real-time risk lookup

#### portfolio_impact (dict)
- **Required fields:** 7 fields including `total_monthly_revenue_at_risk`, `products_at_risk`, `percent_portfolio_at_risk`
- **Usage:** Dashboard KPI card showing total revenue at risk

#### alerts (list)
- **Structure:** List of dicts, one per CRITICAL or HIGH product, sorted by risk_score descending
- **Usage:** Dashboard alerts panel (displays top 10)

#### risk_trends (list)
- **Structure:** List of dicts, one per month, with sentiment and rating aggregates
- **Usage:** Sentiment over time chart

#### global_themes (dict)
- **Structure:** Dict mapping theme names to counts, sorted by count descending
- **Usage:** Top complaint themes display

### 5. Training Pipeline Flow

**Input:** `cleaned_train_80_percent` table from PostgreSQL database

**Processing Steps:**
1. Sentiment Analysis → Add 5 columns to DataFrame
2. TF-IDF Training → Train vectorizer on negative reviews (optional)
3. Risk Scoring → Group by product, calculate 6 sub-scores, weighted composite
4. Revenue Impact → Convert risk scores to financial estimates
5. Aggregation → Portfolio totals, alerts filtering, trends, themes
6. Serialization → Pickle dump to `src/models/Risk_Model_Artifacts.pkl`

**Output:** Artifact file (~5-50 MB depending on review count)

**Execution Time:** ~30-90 seconds for 15,000 reviews

### 6. Validation Interface

**Input:** Trained artifact + `cleaned_test_20_percent` table

**Metrics Computed:**
- Pearson correlation (train vs test risk scores)
- Directional accuracy (high-risk products stay high-risk)
- High-risk recall (% of test high-risk caught in training)
- Score drift (average score shift)
- Time-to-detection advantage (months earlier than simple threshold)

**Output:** `Validation_Report.json` with 8 metrics

### 7. Real-Time Prediction

**Endpoint:** `POST /api/analyze`

**Flow:**
1. Accept new review JSON (text, title, rating, asin)
2. Build single-row DataFrame
3. Run sentiment analysis
4. Extract themes
5. Lookup product risk from artifact
6. Return sentiment score, label, themes, and current product risk

**Response Time:** ~50-200ms (in-memory operations)

---

## Interface Contract Summary

### MANDATORY Requirements

An alternative training algorithm **MUST** produce:

✅ **File format:** Python pickle dictionary at `src/models/Risk_Model_Artifacts.pkl`

✅ **Required keys:** enriched_df, risk_results, portfolio_impact, alerts, risk_trends, global_themes

✅ **Data types:** Exact types match specification (DataFrame, dict, list)

✅ **Schema compliance:**
- enriched_df: 12 required columns with correct types
- risk_results: Per-product dicts with 10 required fields
- portfolio_impact: 7 required aggregated fields
- alerts: List of dicts for CRITICAL/HIGH products only
- risk_trends: List of monthly aggregates
- global_themes: Dict of theme counts

✅ **Value ranges:**
- risk_score: 0-100 (float) or None
- alert_level: One of 5 valid strings
- combined_sentiment: -1.0 to +1.0
- sentiment_label: 'positive', 'negative', or 'neutral'

### OPTIONAL Enhancements

🔲 tfidf_vectorizer: Can be None
🔲 Additional DataFrame columns: Ignored by dashboard
🔲 Additional risk_results fields: Ignored by dashboard
🔲 Custom sub-score names: Dashboard displays whatever is present
🔲 Custom theme categories: Any string names supported

### BREAKING Changes

The following changes **WILL BREAK** the dashboard:

❌ Missing required artifact keys
❌ Wrong data types (e.g., list instead of dict)
❌ Missing required DataFrame columns
❌ Missing required risk_results fields
❌ risk_score outside 0-100 or wrong type
❌ alert_level not in valid set
❌ Unpicklable objects (DB connections, file handles)

---

## Replacing the Training Algorithm

### Step-by-Step Process

1. **Understand Current Baseline**
   - Read `src/Train_Model.py` for full pipeline
   - Review `Risk_Score_Engine.py` for scoring logic
   - Study artifact schema in specification

2. **Implement Your Algorithm**
   - Use any ML framework (PyTorch, TensorFlow, XGBoost, etc.)
   - Process input data to predict risk scores per product
   - Extract or generate interpretable sub-scores
   - Classify complaint themes (keyword, LLM, or clustering)

3. **Map Outputs to Schema**
   - Convert predictions to 0-100 risk scores
   - Generate alert levels based on thresholds
   - Populate sub_scores dict (6 components recommended)
   - Extract top themes per product

4. **Generate Supporting Artifacts**
   - Process full dataset for enriched_df
   - Calculate revenue impact using standard formula
   - Aggregate portfolio metrics
   - Filter alerts (CRITICAL + HIGH only)
   - Compute monthly trends
   - Count global themes

5. **Serialize and Validate**
   - Pickle dump to correct path
   - Run validation checklist (see specification)
   - Start Flask server and verify dashboard

6. **Test All Endpoints**
   - Hit each API route and verify responses
   - Check UI for visual correctness
   - Test real-time analysis
   - Verify chatbot responses

### Example: Deep Learning Replacement

```python
import torch
import pickle
import pandas as pd

# Load your trained model
model = torch.load("my_risk_model.pt")

# Load data
df = pd.read_sql("SELECT * FROM cleaned_train_80_percent", conn)

# Run inference
predictions = model.predict(df)

# Build risk_results matching schema
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
            "model_confidence": float(predictions[...]['confidence'].mean()),
            # Add 5 more interpretable scores
        },
        "top_themes": extract_themes_with_llm(group['text']),
        "average_rating": float(group['average_rating'].iloc[0]),
        "price": float(group['price'].iloc[0]) if 'price' in group else None,
        "revenue_impact": calculate_revenue_impact(score),
    }

# Build full artifact
artifacts = {
    "enriched_df": df_with_sentiment,
    "risk_results": risk_results,
    "portfolio_impact": calculate_portfolio_impact(risk_results),
    "alerts": generate_alerts(risk_results),
    "risk_trends": compute_risk_trends(df_with_sentiment),
    "global_themes": extract_global_themes(df_with_sentiment),
    "tfidf_vectorizer": None,
}

# Save
with open("src/models/Risk_Model_Artifacts.pkl", "wb") as f:
    pickle.dump(artifacts, f)
```

---

## Testing Checklist

Before deploying a new training algorithm:

### Artifact Structure
- [ ] File exists at `src/models/Risk_Model_Artifacts.pkl`
- [ ] Can load with `pickle.load()`
- [ ] All 6 required keys present
- [ ] No unpicklable objects

### Data Types
- [ ] enriched_df is DataFrame with 12+ columns
- [ ] risk_results is dict with ASIN keys
- [ ] portfolio_impact is dict with 7 fields
- [ ] alerts is list of dicts
- [ ] risk_trends is list of dicts
- [ ] global_themes is dict

### Value Ranges
- [ ] risk_score: 0-100 or None
- [ ] alert_level: valid string
- [ ] combined_sentiment: -1.0 to 1.0
- [ ] All financials non-negative

### Dashboard Functionality
- [ ] Dashboard loads without errors
- [ ] KPI cards show values
- [ ] Product table renders
- [ ] Product detail works
- [ ] Trend charts display
- [ ] Alerts panel populates
- [ ] Real-time analysis responds
- [ ] Chatbot returns summaries

### Performance
- [ ] Artifact size < 100 MB
- [ ] Server startup < 10 seconds
- [ ] API responses < 1 second

---

## Documentation Deliverables

Three comprehensive documents have been created:

1. **ML_ARTIFACT_INTERFACE_SPECIFICATION.md** (12,000+ words)
   - Complete technical specification
   - Field-by-field schema definitions
   - Code references and line numbers
   - Validation requirements
   - Interface contract details

2. **ML_ARTIFACT_DATA_FLOW.md** (5,000+ words)
   - Visual ASCII diagrams
   - Data flow charts
   - Dependency maps
   - Size optimization tips
   - Troubleshooting guide

3. **ML_ARTIFACT_QUICK_REFERENCE.md** (2,500+ words)
   - Single-page reference card
   - Quick lookup tables
   - Command reference
   - Common errors and fixes
   - Testing commands

---

## Key Insights

### 1. Tight Coupling to Schema

The dashboard is **schema-dependent** but **algorithm-agnostic**. Any ML approach works as long as outputs conform to the artifact schema.

### 2. No Real-Time Model Updates

The artifact is loaded once at startup. To deploy a new model, the Flask server must be restarted. No hot reload capability exists.

### 3. Revenue Impact is Templated

Revenue calculations use a **fixed formula** based on:
- Company revenue: $2.8B annually
- Products: 40
- Average product revenue: $5.83M/month
- Max risk impact: 15%
- Recovery rate: 70%

This can be overridden in the `revenue_impact` field if custom logic is used.

### 4. Sub-Scores are Flexible

The dashboard displays whatever sub-scores are present in the `sub_scores` dict. The current implementation uses 6 specific components with predefined weights, but alternative models can use different sub-score names and counts.

### 5. Theme Extraction is Keyword-Based

Current theme extraction uses keyword matching against 10 predefined categories (battery, overheating, screen, etc.). Alternative models can use:
- LLM-based classification
- Topic modeling (LDA, NMF)
- Clustering
- Zero-shot classification

As long as the output format matches (list of tuples with theme names and frequencies).

### 6. Validation is Business-Focused

Validation metrics prioritize **business-risk stability** over traditional ML classification metrics:
- Pearson correlation (score consistency)
- Directional accuracy (high-risk stays high-risk)
- High-risk recall (catch critical products)
- Time-to-detection advantage (vs simple threshold)

No accuracy, precision, recall, F1, or AUC metrics are used.

### 7. Dataset is Product-Diverse

The system handles products with **varying review counts** (minimum 3 reviews for scoring). Products with insufficient data receive `risk_score: None` and `alert_level: "INSUFFICIENT DATA"`.

### 8. Artifacts are Serialization-Complete

The artifact contains **everything** needed for dashboard operation. No additional database queries are required for dashboard rendering (except for new review submission).

---

## Recommendations

### For ML Engineers Replacing the Algorithm

1. **Start with schema compliance:** Ensure your outputs match the artifact structure before optimizing model accuracy
2. **Test incrementally:** Verify each artifact key independently before combining
3. **Use validation pipeline:** Run `Validate_Model.py` after every training run to catch schema issues early
4. **Preserve business metrics:** Even if using a different algorithm, maintain revenue impact calculations for business stakeholder alignment
5. **Document sub-scores:** If changing sub-score definitions, document what each one represents for interpretability

### For System Maintainers

1. **Version artifacts:** Save artifacts with timestamps for rollback capability
2. **Monitor drift:** Track validation metrics over time to detect degradation
3. **Implement hot reload:** Consider adding artifact reload endpoint to avoid server restarts
4. **Add schema validation:** Implement explicit schema checks at artifact load time
5. **Log artifact stats:** Record file size, record counts, and load times for monitoring

### For Dashboard Developers

1. **Defensive coding:** Add null checks and type guards when accessing artifact data
2. **Graceful degradation:** Handle missing optional fields cleanly
3. **Error boundaries:** Catch artifact load failures and show informative messages
4. **Performance optimization:** Consider caching expensive artifact computations (e.g., aggregations)
5. **API versioning:** If breaking schema changes are needed, version the API endpoints

---

## Conclusion

The ML artifact serves as a **clean interface contract** between the training pipeline and the dashboard backend. By adhering to the documented schema, any ML algorithm—from simple heuristics to deep learning—can power the FusionTech Product Risk Management System without requiring dashboard code changes.

The three documentation files provide:
- **Specification:** Complete technical reference for developers
- **Data Flow:** Visual understanding of system architecture
- **Quick Reference:** Practical lookup guide for daily use

With these resources, a developer can confidently implement a new training algorithm, validate its compatibility, and deploy it to production with minimal integration effort.

---

**Analysis Complete**

**Created Documents:**
1. `ML_ARTIFACT_INTERFACE_SPECIFICATION.md`
2. `ML_ARTIFACT_DATA_FLOW.md`
3. `ML_ARTIFACT_QUICK_REFERENCE.md`
4. `ML_ARTIFACT_ANALYSIS_SUMMARY.md` (this document)

**Total Documentation:** ~20,000 words

**Repository:** `/c:/Users/mayan/OneDrive/Documents/GitHub/excelwithdell/`

---

*For questions or clarifications, refer to the detailed specification document or examine the source code files listed in the code references section.*
