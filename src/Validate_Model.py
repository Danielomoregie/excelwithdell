import os
import pickle
import json
import pandas as pd
import numpy as np

from Neon_Accessibility_Helper_Functions import get_connection, close_connection
from Sentiment_Analyzer import analyze_sentiment
from Risk_Score_Engine import compute_product_risk_scores
from Revenue_Impact_Calculator import calculate_revenue_impact, AVG_PRODUCT_MONTHLY_REVENUE

# ==============================
# CONFIGURATION
# ==============================

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")
TESTING_TABLE = "cleaned_test_20_percent"
VALIDATION_REPORT_PATH = os.path.join(MODELS_DIR, "Validation_Report.json")


# ==============================
# VALIDATION PIPELINE
# ==============================

def main():
    print("=" * 60)
    print("  FusionTech Product Risk Model - Validation")
    print("=" * 60)

    # ---- Load training artifacts ----
    print("\n[1/5] Loading trained model artifacts...")
    if not os.path.exists(ARTIFACTS_PATH):
        print("ERROR: No trained model found. Run Train_Model.py first.")
        return

    with open(ARTIFACTS_PATH, "rb") as f:
        artifacts = pickle.load(f)

    train_risk = artifacts['risk_results']
    print(f"       Loaded risk scores for {len(train_risk)} products")

    # ---- Pull test data ----
    print("\n[2/5] Pulling test data from Neon...")
    conn = get_connection()
    test_df = pd.read_sql(
        f"SELECT * FROM {TESTING_TABLE} ORDER BY date ASC",
        conn
    )
    close_connection(conn)
    print(f"       Loaded {len(test_df)} test reviews")

    if 'date' in test_df.columns:
        test_df['date'] = pd.to_datetime(test_df['date'], errors='coerce')

    # ---- Analyze test set ----
    print("\n[3/5] Running sentiment analysis on test data...")
    test_enriched = analyze_sentiment(test_df)

    # ---- Compute test-period risk scores ----
    print("\n[4/5] Computing test-period risk scores...")
    test_risk = compute_product_risk_scores(test_enriched)

    # ---- Compare training vs test ----
    print("\n[5/5] Comparing training predictions vs test outcomes...")

    # Find products that appear in both train and test
    common_asins = set(train_risk.keys()) & set(test_risk.keys())
    # Only compare products that have scores in both periods
    comparable = [
        asin for asin in common_asins
        if train_risk[asin]['risk_score'] is not None
        and test_risk[asin]['risk_score'] is not None
    ]

    print(f"\n       Products in both train and test periods: {len(common_asins)}")
    print(f"       Products with scores in both periods: {len(comparable)}")

    if len(comparable) < 3:
        print("\n       Not enough comparable products for statistical validation.")
        print("       This is expected with a small, product-diverse dataset.")
        _print_qualitative_analysis(train_risk, test_risk, test_enriched, common_asins)
        return

    # --- Metric 1: Pearson Correlation ---
    train_scores = [train_risk[a]['risk_score'] for a in comparable]
    test_scores = [test_risk[a]['risk_score'] for a in comparable]
    correlation = np.corrcoef(train_scores, test_scores)[0, 1]

    # --- Metric 2: Directional Accuracy ---
    # If train risk was above median, did test risk stay above median?
    train_median = np.median(train_scores)
    test_median = np.median(test_scores)
    correct_direction = sum(
        1 for a in comparable
        if (train_risk[a]['risk_score'] >= train_median) ==
           (test_risk[a]['risk_score'] >= test_median)
    )
    directional_accuracy = correct_direction / len(comparable)

    # --- Metric 3: High-Risk Recall ---
    # Of the products that were actually high-risk in test period,
    # how many did we flag in training?
    test_high_risk = [a for a in comparable if test_risk[a]['risk_score'] >= 50]
    if test_high_risk:
        caught = sum(1 for a in test_high_risk if train_risk[a]['risk_score'] >= 40)
        high_risk_recall = caught / len(test_high_risk)
    else:
        high_risk_recall = 1.0  # No high-risk products to miss

    # --- Metric 4: Average Score Drift ---
    avg_train = np.mean(train_scores)
    avg_test = np.mean(test_scores)
    score_drift = avg_test - avg_train

    # --- Metric 5: Time-to-Detection Advantage ---
    # How much earlier does the model flag vs simple "avg rating < 3.0"?
    time_advantage = _compute_time_advantage(test_enriched, train_risk)

    report = {
        "products_compared": len(comparable),
        "pearson_correlation": round(float(correlation), 4) if not np.isnan(correlation) else 0,
        "directional_accuracy": round(directional_accuracy, 4),
        "high_risk_recall": round(high_risk_recall, 4),
        "test_high_risk_count": len(test_high_risk),
        "avg_train_risk_score": round(avg_train, 2),
        "avg_test_risk_score": round(avg_test, 2),
        "score_drift": round(score_drift, 2),
        "time_advantage_months": time_advantage,
    }

    # Print results
    print("\n" + "-" * 50)
    print("  VALIDATION RESULTS")
    print("-" * 50)
    print(f"  Pearson Correlation:    {report['pearson_correlation']:.4f}")
    print(f"  Directional Accuracy:   {report['directional_accuracy']:.1%}")
    print(f"  High-Risk Recall:       {report['high_risk_recall']:.1%} "
          f"({len(test_high_risk)} high-risk products in test)")
    print(f"  Avg Train Risk Score:   {report['avg_train_risk_score']}")
    print(f"  Avg Test Risk Score:    {report['avg_test_risk_score']}")
    print(f"  Score Drift:            {report['score_drift']:+.2f}")
    print(f"  Time Advantage:         ~{report['time_advantage_months']} months earlier detection")
    print("-" * 50)

    # --- Revenue Impact Replay ---
    print("\n  HISTORICAL REVENUE IMPACT REPLAY:")
    _revenue_replay(train_risk, test_risk, comparable, time_advantage)

    # Save report
    with open(VALIDATION_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Validation report saved to: {VALIDATION_REPORT_PATH}")

    print("\n" + "=" * 60)
    print("  Validation complete!")
    print("=" * 60)


def _compute_time_advantage(test_enriched, train_risk):
    """
    Estimate how many months earlier the model would flag issues
    vs. a simple threshold approach (e.g., avg rating drops below 3.0).
    """
    # Look at products that the model flagged as high risk in training
    flagged = [a for a, r in train_risk.items()
               if r['risk_score'] is not None and r['risk_score'] >= 50]

    if not flagged:
        return 0

    advantages = []
    for asin in flagged:
        product_test = test_enriched[test_enriched['asin'] == asin].sort_values('date')
        if len(product_test) < 3:
            continue

        # When would a simple threshold have caught it?
        # Rolling 3-review average rating
        product_test = product_test.copy()
        product_test['rolling_avg'] = product_test['rating'].astype(float).rolling(3, min_periods=1).mean()
        below_threshold = product_test[product_test['rolling_avg'] < 3.0]

        if below_threshold.empty:
            advantages.append(3)  # Model caught it but simple threshold never would
        else:
            # Model caught it at the start of test period;
            # simple threshold caught it when rolling avg dropped
            first_flag = product_test['date'].iloc[0]
            threshold_flag = below_threshold['date'].iloc[0]
            diff = (threshold_flag - first_flag).days / 30  # Convert to months
            advantages.append(max(0, round(diff)))

    return round(np.mean(advantages)) if advantages else 0


def _revenue_replay(train_risk, test_risk, comparable, time_advantage_months):
    """
    Calculate estimated revenue saved by early detection.
    """
    total_savings = 0
    for asin in comparable:
        train_score = train_risk[asin]['risk_score']
        test_score = test_risk[asin]['risk_score']

        # Products where risk was flagged early (train) and confirmed (test)
        if train_score >= 40 and test_score >= 40:
            impact = calculate_revenue_impact(test_score)
            monthly_savings = impact['potential_monthly_savings']
            product_savings = monthly_savings * max(time_advantage_months, 1)
            total_savings += product_savings

    print(f"  Estimated revenue protected by early detection:")
    print(f"  ${total_savings:,.0f} over {time_advantage_months} month(s)")
    print(f"  (Based on {len(comparable)} products with data in both periods)")


def _print_qualitative_analysis(train_risk, test_risk, test_enriched, common_asins):
    """Print qualitative analysis when not enough products for stats."""
    print("\n  QUALITATIVE ANALYSIS:")
    for asin in list(common_asins)[:10]:
        train_data = train_risk.get(asin, {})
        test_data = test_risk.get(asin, {})
        train_score = train_data.get('risk_score')
        test_score = test_data.get('risk_score')
        name = train_data.get('product_name', 'Unknown')[:40]

        test_reviews = test_enriched[test_enriched['asin'] == asin]
        test_neg_ratio = (test_reviews['sentiment_label'] == 'negative').mean() if len(test_reviews) > 0 else 0

        print(f"\n  {name}")
        print(f"    Train Risk: {train_score} | Test Risk: {test_score} | "
              f"Test Negative Ratio: {test_neg_ratio:.1%}")


if __name__ == "__main__":
    main()
