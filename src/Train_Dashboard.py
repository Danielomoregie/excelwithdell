"""
Train_Dashboard.py
------------------
Trains the same risk model pipeline as Train_Model.py but on 100% of the
online_reviews data (no train/test split) and saves the result to:

    src/models/dashboard.pkl

Nothing else is touched: no model_registry.json, no Validation_Report.json,
no current_production_model.pkl, no baseline_metrics.json.

The operating_high_risk_threshold is carried over from the existing
current_production_model.pkl so the dashboard threshold stays calibrated.

Usage:
    cd src
    python Train_Dashboard.py
"""

import os
import sys
import pickle

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from Neon_Accessibility_Helper_Functions import get_connection, close_connection
from Sentiment_Analyzer import analyze_sentiment
from Theme_Extractor import train_tfidf_model, get_global_theme_counts
from Risk_Score_Engine import (
    compute_product_risk_scores,
    compute_risk_trends,
    generate_alerts,
    ALERT_THRESHOLDS,
)
from Revenue_Impact_Calculator import (
    calculate_revenue_impact,
    calculate_portfolio_impact,
    TOTAL_ANNUAL_REVENUE,
    MONTHLY_REVENUE,
    NUM_PRODUCTS,
    AVG_PRODUCT_MONTHLY_REVENUE,
    MAX_RISK_IMPACT_PERCENT,
    DEFAULT_RECOVERY_RATE,
)

# ── paths ──────────────────────────────────────────────────────────────────────

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
DASHBOARD_PKL = os.path.join(MODELS_DIR, "dashboard.pkl")
D2_PKL = os.path.join(MODELS_DIR, "d2.pkl")
D3_PKL = os.path.join(MODELS_DIR, "d3.pkl")
PRODUCTION_PKL = os.path.join(MODELS_DIR, "current_production_model.pkl")

TRAINING_TABLE = "online_reviews"


def _load_calibrated_threshold() -> float:
    """Read operating_high_risk_threshold from the existing production pkl."""
    try:
        with open(PRODUCTION_PKL, "rb") as f:
            prod = pickle.load(f)
        threshold = (prod.get("model_metadata") or {}).get("operating_high_risk_threshold")
        if threshold is not None:
            return float(threshold)
    except Exception:
        pass
    return float(ALERT_THRESHOLDS.get("high", 50))


def main():
    print("=" * 60)
    print("  FusionTech Dashboard PKL - Full-Data Training")
    print("=" * 60)

    calibrated_threshold = _load_calibrated_threshold()
    print(f"\n  Using calibrated threshold: {calibrated_threshold}")

    # ── Step 1: load ALL data from CSV ─────────────────────────────────────────
    print("\n[1/6] Loading full dataset from CSV file...")
    csv_path = os.path.join(os.path.dirname(__file__), "..", "Dataset_Scripts", "CSV_Files", "FusionTech_2014_06_to_2022_06_Initial.csv")
    df = pd.read_csv(csv_path)
    print(f"       Loaded {len(df)} reviews from FusionTech_2014_06_to_2022_06_Initial.csv")

    # Ensure date column exists and is datetime
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # ── Step 2: sentiment ─────────────────────────────────────────────────────
    print("\n[2/6] Running VADER sentiment analysis...")
    enriched_df = analyze_sentiment(df)
    pos = (enriched_df["sentiment_label"] == "positive").sum()
    neg = (enriched_df["sentiment_label"] == "negative").sum()
    neu = (enriched_df["sentiment_label"] == "neutral").sum()
    print(f"       Positive: {pos} | Negative: {neg} | Neutral: {neu}")

    # ── Step 3: TF-IDF ────────────────────────────────────────────────────────
    print("\n[3/6] Training TF-IDF vectorizer on negative reviews...")
    tfidf_vectorizer, feature_names = train_tfidf_model(enriched_df)
    if tfidf_vectorizer:
        print(f"       Vocabulary size: {len(feature_names)} terms")
    else:
        print("       Not enough negative reviews to train TF-IDF.")

    # ── Step 4: risk scores ───────────────────────────────────────────────────
    print("\n[4/6] Computing product risk scores...")
    risk_results = compute_product_risk_scores(enriched_df)
    scored = sum(1 for r in risk_results.values() if r["risk_score"] is not None)
    print(f"       Products scored: {scored}")

    top5 = sorted(
        [r for r in risk_results.values() if r["risk_score"] is not None],
        key=lambda x: x["risk_score"],
        reverse=True,
    )[:5]
    print("\n       Top 5 Riskiest Products:")
    for i, p in enumerate(top5):
        themes = ", ".join(t[0] for t in p["top_themes"][:3]) or "none"
        print(f"       {i+1}. [{p['alert_level']}] {p['risk_score']} | "
              f"{p['product_name'][:50]} | {themes}")

    # ── Step 5: revenue impact ────────────────────────────────────────────────
    print("\n[5/6] Calculating revenue impact...")
    for asin, data in risk_results.items():
        data["revenue_impact"] = calculate_revenue_impact(data["risk_score"])
    portfolio = calculate_portfolio_impact(risk_results)
    print(f"       Monthly revenue at risk:  ${portfolio['total_monthly_revenue_at_risk']:,.0f}")
    print(f"       Potential monthly savings: ${portfolio['total_potential_monthly_savings']:,.0f}")

    # ── Step 6: trends, themes, alerts ───────────────────────────────────────
    # Determine output file: d2.pkl if --d2 or d2 argument is given, else dashboard.pkl
    use_d2 = False
    use_d3 = False
    if len(sys.argv) > 1:
        if sys.argv[1] in ('--d2', 'd2'):
            use_d2 = True
        elif sys.argv[1] in ('--d3', 'd3'):
            use_d3 = True
    if use_d3:
        out_pkl = D3_PKL
        out_label = 'd3.pkl'
    elif use_d2:
        out_pkl = D2_PKL
        out_label = 'd2.pkl'
    else:
        out_pkl = DASHBOARD_PKL
        out_label = 'dashboard.pkl'
    print(f"\n[6/6] Computing trends and saving {out_label}...")
    risk_trends = compute_risk_trends(enriched_df)
    global_themes = get_global_theme_counts(enriched_df)
    alerts = generate_alerts(risk_results)

    artifacts = {
        "enriched_df": enriched_df,
        "tfidf_vectorizer": tfidf_vectorizer,
        "risk_results": risk_results,
        "risk_trends": risk_trends,
        "global_themes": global_themes,
        "alerts": alerts,
        "portfolio_impact": portfolio,
        "model_metadata": {
            "model_name": "hybrid-risk-v2",
            "model_type": "rule_based_with_bayesian_smoothing",
            "training_table": TRAINING_TABLE,
            "training_coverage": "100%",
            "min_reviews": 3,
            "risk_thresholds": ALERT_THRESHOLDS,
            "operating_high_risk_threshold": calibrated_threshold,
            "subscore_weights": {
                "negative_sentiment_ratio": 0.25,
                "sentiment_velocity": 0.15,
                "rating_decline": 0.20,
                "low_rating_spike": 0.15,
                "complaint_concentration": 0.10,
                "community_validated": 0.15,
            },
            "financial_assumptions": {
                "total_annual_revenue": TOTAL_ANNUAL_REVENUE,
                "company_monthly_revenue": MONTHLY_REVENUE,
                "num_products": NUM_PRODUCTS,
                "avg_product_monthly_revenue": AVG_PRODUCT_MONTHLY_REVENUE,
                "max_risk_impact_percent": MAX_RISK_IMPACT_PERCENT,
                "default_recovery_rate": DEFAULT_RECOVERY_RATE,
            },
            "notes": "Trained on 100% of online_reviews. Threshold carried from production model.",
        },
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(out_pkl, "wb") as f:
        pickle.dump(artifacts, f)

    size_mb = os.path.getsize(out_pkl) / (1024 * 1024)
    print(f"\n  Saved: {out_pkl} ({size_mb:.1f} MB)")
    print(f"  Done. {out_label} is ready.")


if __name__ == "__main__":
    main()
