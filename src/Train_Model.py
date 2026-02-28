import os
import sys
import pickle
import pandas as pd

from Neon_Accessibility_Helper_Functions import get_connection, close_connection
from Sentiment_Analyzer import analyze_sentiment
from Theme_Extractor import train_tfidf_model, extract_themes, get_global_theme_counts
from Risk_Score_Engine import compute_product_risk_scores, compute_risk_trends, generate_alerts
from Revenue_Impact_Calculator import calculate_revenue_impact, calculate_portfolio_impact

# ==============================
# CONFIGURATION
# ==============================

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")
TRAINING_TABLE = "cleaned_train_80_percent"


# ==============================
# MAIN TRAINING PIPELINE
# ==============================

def main():
    print("=" * 60)
    print("  FusionTech Product Risk Model - Training Pipeline")
    print("=" * 60)

    # ---- Step 1: Pull training data from Neon ----
    print("\n[1/6] Connecting to Neon and pulling training data...")
    conn = get_connection()
    train_df = pd.read_sql(
        f"SELECT * FROM {TRAINING_TABLE} ORDER BY date ASC",
        conn
    )
    close_connection(conn)
    print(f"       Loaded {len(train_df)} reviews from '{TRAINING_TABLE}'")

    # Ensure date column is datetime
    if 'date' in train_df.columns:
        train_df['date'] = pd.to_datetime(train_df['date'], errors='coerce')

    # ---- Step 2: Run sentiment analysis ----
    print("\n[2/6] Running VADER sentiment analysis...")
    enriched_df = analyze_sentiment(train_df)

    pos = (enriched_df['sentiment_label'] == 'positive').sum()
    neg = (enriched_df['sentiment_label'] == 'negative').sum()
    neu = (enriched_df['sentiment_label'] == 'neutral').sum()
    print(f"       Positive: {pos} | Negative: {neg} | Neutral: {neu}")

    # ---- Step 3: Train TF-IDF model ----
    print("\n[3/6] Training TF-IDF vectorizer on negative reviews...")
    tfidf_vectorizer, feature_names = train_tfidf_model(enriched_df)
    if tfidf_vectorizer:
        print(f"       Vocabulary size: {len(feature_names)} terms")
    else:
        print("       Not enough negative reviews to train TF-IDF.")

    # ---- Step 4: Extract themes + compute risk scores ----
    print("\n[4/6] Computing product risk scores...")
    risk_results = compute_product_risk_scores(enriched_df)

    scored = sum(1 for r in risk_results.values() if r['risk_score'] is not None)
    insufficient = sum(1 for r in risk_results.values() if r['risk_score'] is None)
    print(f"       Products scored: {scored} | Insufficient data: {insufficient}")

    # Print top 5 riskiest
    scored_products = [r for r in risk_results.values() if r['risk_score'] is not None]
    scored_products.sort(key=lambda x: x['risk_score'], reverse=True)
    print("\n       Top 5 Riskiest Products:")
    for i, p in enumerate(scored_products[:5]):
        themes = ", ".join(t[0] for t in p['top_themes'][:3]) or "none detected"
        print(f"       {i+1}. [{p['alert_level']}] Score: {p['risk_score']} | "
              f"{p['product_name'][:50]} | Themes: {themes}")

    # ---- Step 5: Add revenue impact to each product ----
    print("\n[5/6] Calculating revenue impact estimates...")
    for asin, data in risk_results.items():
        data['revenue_impact'] = calculate_revenue_impact(data['risk_score'])

    portfolio = calculate_portfolio_impact(risk_results)
    print(f"       Total monthly revenue at risk: ${portfolio['total_monthly_revenue_at_risk']:,.0f}")
    print(f"       Potential monthly savings: ${portfolio['total_potential_monthly_savings']:,.0f}")

    # ---- Step 6: Compute trends + save everything ----
    print("\n[6/6] Computing trends and saving artifacts...")
    risk_trends = compute_risk_trends(enriched_df)
    global_themes = get_global_theme_counts(enriched_df)
    alerts = generate_alerts(risk_results)

    # Build artifacts bundle
    artifacts = {
        "enriched_df": enriched_df,
        "tfidf_vectorizer": tfidf_vectorizer,
        "risk_results": risk_results,
        "risk_trends": risk_trends,
        "global_themes": global_themes,
        "alerts": alerts,
        "portfolio_impact": portfolio,
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(ARTIFACTS_PATH, "wb") as f:
        pickle.dump(artifacts, f)

    file_size_mb = os.path.getsize(ARTIFACTS_PATH) / (1024 * 1024)
    print(f"       Saved to: {ARTIFACTS_PATH} ({file_size_mb:.1f} MB)")

    print("\n" + "=" * 60)
    print("  Training complete!")
    print(f"  {scored} products scored | {len(alerts)} alerts generated")
    print("=" * 60)

    return artifacts


if __name__ == "__main__":
    main()
