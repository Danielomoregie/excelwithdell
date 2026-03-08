# ML Artifact Interface - Quick Reference Card

**File:** `src/models/Risk_Model_Artifacts.pkl`  
**Format:** Python pickle dictionary  
**Loaded:** Once at Flask server startup

---

## Required Artifact Keys

```python
artifacts = {
    "enriched_df": pandas.DataFrame,     # Full review dataset + sentiment
    "risk_results": dict,                # Per-product risk scores
    "portfolio_impact": dict,            # Aggregate revenue impact
    "alerts": list,                      # CRITICAL + HIGH products only
    "risk_trends": list,                 # Monthly sentiment trends
    "global_themes": dict,               # Complaint theme counts
    "tfidf_vectorizer": object or None,  # Optional: sklearn vectorizer
}
```

---

## enriched_df Columns (Required)

| Column | Type | Range/Values |
|--------|------|--------------|
| `asin` | str | Product ID |
| `text` | str | Original review text |
| `title_x` | str | Review title |
| `rating` | float | 1.0 - 5.0 |
| `date` | datetime64 | Any valid date |
| `sentiment_label` | str | 'positive', 'negative', 'neutral' |
| `combined_sentiment` | float | -1.0 to +1.0 |
| `text_cleaned` | str | No HTML, normalized |
| `helpful_vote` | int/float | ≥ 0 |
| `average_rating` | float | Product's overall rating |
| `title_y` | str | Product name |
| `price` | float | USD price (nullable) |

---

## risk_results Structure

```python
{
  "B01ABC1234": {
    # Core (REQUIRED)
    "asin": str,
    "product_name": str,              # Max 80 chars
    "risk_score": float or None,      # 0-100 or None
    "alert_level": str,               # See levels below
    "review_count": int,
    "average_rating": float or None,
    "price": float or None,
    
    # Sub-scores (REQUIRED dict with 6 keys)
    "sub_scores": {
      "negative_sentiment_ratio": float,    # 0-100
      "sentiment_velocity": float,          # 0-100
      "rating_decline": float,              # 0-100
      "low_rating_spike": float,            # 0-100
      "complaint_concentration": float,     # 0-100
      "community_validated": float,         # 0-100
    },
    
    # Themes (REQUIRED list of tuples)
    "top_themes": [("theme_name", frequency_ratio), ...],
    
    # Revenue (REQUIRED dict with 5 keys)
    "revenue_impact": {
      "monthly_revenue_at_risk": float,
      "annualized_revenue_at_risk": float,
      "potential_monthly_savings": float,
      "potential_annual_savings": float,
      "risk_factor_percent": float,
    },
  }
}
```

---

## Alert Levels

| Level | Risk Score Range | Action |
|-------|------------------|--------|
| `"CRITICAL"` | 75-100 | Immediate escalation |
| `"HIGH"` | 50-74.9 | Investigate themes |
| `"MODERATE"` | 25-49.9 | Monitor trends |
| `"LOW"` | 0-24.9 | No action needed |
| `"INSUFFICIENT DATA"` | None (< 3 reviews) | Wait for more data |

---

## portfolio_impact Structure

```python
{
  "total_monthly_revenue_at_risk": float,
  "total_annual_revenue_at_risk": float,
  "total_potential_monthly_savings": float,
  "total_potential_annual_savings": float,
  "products_at_risk": int,
  "company_monthly_revenue": float,
  "percent_portfolio_at_risk": float,
}
```

---

## alerts Structure

```python
[
  {
    "asin": str,
    "product_name": str,
    "risk_score": float,
    "alert_level": str,               # Only "CRITICAL" or "HIGH"
    "top_themes": [str, str, ...],    # List of theme names (NOT tuples)
    "review_count": int,
  },
  # ... sorted by risk_score descending
]
```

---

## risk_trends Structure

```python
[
  {
    "month": str,                  # Format: "2022-01"
    "avg_sentiment": float,        # Mean sentiment for month
    "negative_ratio": float,       # 0.0 - 1.0
    "review_count": int,
    "avg_rating": float,           # 1.0 - 5.0
  },
  # ... sorted by month ascending
]
```

---

## global_themes Structure

```python
{
  "battery": 142,
  "overheating": 98,
  "screen": 87,
  # ... sorted by count descending
}
```

---

## Dashboard Endpoint Usage

| Endpoint | Keys Accessed |
|----------|---------------|
| `/api/dashboard` | risk_results, portfolio_impact, alerts, enriched_df |
| `/api/products` | risk_results |
| `/api/products/<asin>` | risk_results, enriched_df |
| `/api/trends` | risk_trends, global_themes |
| `/api/analyze` | enriched_df, risk_results |
| `/api/chatbot` | risk_results |

---

## Training Pipeline Checklist

- [ ] Load data from `cleaned_train_80_percent` table
- [ ] Add sentiment columns to DataFrame
- [ ] Group by ASIN and compute risk scores (0-100)
- [ ] Map risk scores to alert levels
- [ ] Extract top complaint themes per product
- [ ] Calculate revenue impact per product
- [ ] Aggregate portfolio impact
- [ ] Filter alerts (CRITICAL + HIGH only)
- [ ] Compute monthly trends
- [ ] Count global themes
- [ ] Serialize as pickle to `src/models/Risk_Model_Artifacts.pkl`

---

## Validation Checklist

After saving artifact, verify:

- [ ] File exists at correct path
- [ ] Can load with `pickle.load()`
- [ ] All 7 keys present in dictionary
- [ ] `enriched_df` is DataFrame with 12+ required columns
- [ ] `risk_results` has entries (not empty dict)
- [ ] All `risk_score` values are float 0-100 or None
- [ ] All `alert_level` values are valid strings
- [ ] `portfolio_impact` has 7 required fields
- [ ] `alerts` is list (may be empty if no CRITICAL/HIGH)
- [ ] Flask server starts without errors
- [ ] Dashboard loads and displays KPIs

---

## Load Artifact (Python)

```python
import pickle

ARTIFACTS_PATH = "src/models/Risk_Model_Artifacts.pkl"

with open(ARTIFACTS_PATH, "rb") as f:
    artifacts = pickle.load(f)

# Access data
enriched_df = artifacts['enriched_df']
risk_results = artifacts['risk_results']
portfolio = artifacts['portfolio_impact']
alerts = artifacts['alerts']
trends = artifacts['risk_trends']
themes = artifacts['global_themes']
vectorizer = artifacts['tfidf_vectorizer']
```

---

## Save Artifact (Python)

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

## Revenue Impact Formula

```python
AVG_PRODUCT_MONTHLY_REVENUE = $5,833,333
MAX_RISK_IMPACT_PERCENT = 0.15  # 15% max
RECOVERY_RATE = 0.70            # 70% recoverable

risk_factor = (risk_score / 100) * MAX_RISK_IMPACT_PERCENT
monthly_at_risk = AVG_PRODUCT_MONTHLY_REVENUE * risk_factor
potential_savings = monthly_at_risk * RECOVERY_RATE
```

**Example:**
- Risk score: 67.3
- Risk factor: 0.10095 (10.095%)
- Monthly at risk: $588,742
- Potential savings: $412,119

---

## Sub-Score Weights

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

---

## Complaint Theme Categories

Standard themes (keyword-based detection):

- `overheating`: hot, heat, overheat, thermal, fan, temperature
- `battery`: battery, charge, charging, power supply, drain
- `screen`: screen, display, flicker, dead pixel, dim, bright
- `performance`: slow, lag, freeze, crash, hang, boot
- `keyboard`: keyboard, key, typing, trackpad, touchpad
- `build_quality`: cheap, plastic, broken, crack, hinge, flimsy
- `software`: driver, update, windows, bios, bloatware, software
- `connectivity`: wifi, bluetooth, usb, port, adapter, network
- `customer_service`: support, warranty, return, refund, service
- `value`: price, expensive, overpriced, money, worth, cost

---

## Common Errors

| Error | Root Cause | Fix |
|-------|------------|-----|
| "File not found" | Artifact not created | Run `Train_Model.py` |
| "KeyError: 'risk_results'" | Missing artifact key | Check artifact structure |
| "0 products analyzed" | Empty `risk_results` | Lower MIN_REVIEWS threshold |
| "Pickle load error" | Unpicklable object | Remove DB connections, file handles |
| "No sentiment timeline" | `date` not datetime | Convert with `pd.to_datetime()` |

---

## File Size Guidelines

| Component | Typical Size | Optimization |
|-----------|--------------|--------------|
| enriched_df | 80-95% | Use category dtypes, drop unused columns |
| risk_results | 5-10% | Limit theme count, round floats |
| Other keys | <5% | Minimal impact |
| **Total** | **5-50 MB** | Compress with gzip if needed |

---

## Replace Training Algorithm

To use a different ML approach:

1. Load training data from database
2. Implement your prediction logic (any framework)
3. Convert outputs to match artifact schema
4. Populate all required keys and fields
5. Save as pickle to correct path
6. Validate with checklist above
7. Restart Flask server

**The dashboard code does NOT need changes if artifact schema is preserved.**

---

## Testing Commands

```bash
# Train model
python src/Train_Model.py

# Validate model
python src/Validate_Model.py

# Start dashboard
python src/Run_System.py

# Check artifact
python -c "import pickle; a=pickle.load(open('src/models/Risk_Model_Artifacts.pkl','rb')); print('Keys:', a.keys()); print('Products:', len(a['risk_results']))"
```

---

## Documentation Files

- **ML_ARTIFACT_INTERFACE_SPECIFICATION.md**: Full technical specification
- **ML_ARTIFACT_DATA_FLOW.md**: Visual diagrams and flow charts
- **ML_ARTIFACT_QUICK_REFERENCE.md**: This quick reference card

---

**Version:** 1.0 | **Last Updated:** 2026-03-07

*Keep this card handy when implementing or debugging ML artifact integration.*
