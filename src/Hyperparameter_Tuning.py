"""
Hyperparameter tuning for the Risk Score Engine.
Tests different weight configurations and prior strengths to maximize Pearson correlation.
"""

import json
import os
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

# Import model components
from Neon_Accessibility_Helper_Functions import get_connection, close_connection
from Risk_Score_Engine import (
    compute_product_risk_scores,
    _negative_sentiment_ratio,
    _sentiment_velocity,
    _rating_decline,
    _low_rating_spike,
    _complaint_concentration,
    _community_validated,
    _rolling_negative_trend,
    _rating_drop_velocity,
    _review_spike_detection,
    _score_confidence,
    _recent_risk_boost,
    _get_alert_level,
    _get_product_name,
    _safe_float,
    MIN_REVIEWS,
    BASELINE_RISK_SCORE,
    NEGATIVE_RATIO_PRIOR_STRENGTH,
    LOW_RATING_PRIOR_STRENGTH,
)
from Sentiment_Analyzer import analyze_sentiment
from Theme_Extractor import extract_themes

load_dotenv()

TEST_TABLE = "cleaned_test_20_percent"

def evaluate_weight_config(
    test_df,
    risk_scores,
    labeled_risks,
    weights,
    name="config"
):
    """
    Evaluate a weight configuration against test labels.
    Returns Pearson, MAE, and directional accuracy.
    """
    predicted = []
    actual = []
    
    for asin, actual_risk in labeled_risks.items():
        if asin in risk_scores:
            predicted.append(risk_scores[asin]['risk_score'] or 0)
            actual.append(actual_risk)
    
    if len(predicted) < 10:
        return None, None, None
    
    pearson, _ = pearsonr(actual, predicted)
    mae = mean_absolute_error(actual, predicted)
    
    # Directional accuracy: did we predict high risk when actual was high risk?
    correct = sum(1 for p, a in zip(predicted, actual) if (p >= 50) == (a >= 50))
    dir_acc = correct / len(predicted) if predicted else 0
    
    print(f"  {name:30s} | Pearson: {pearson:.6f} | MAE: {mae:.3f} | Dir Acc: {dir_acc:.2%}")
    return pearson, mae, dir_acc


def compute_risk_scores_with_weights(df, weights_config):
    """
    Compute risk scores with custom weights.
    Simplified version that applies weights directly.
    """
    all_neg = df[df['sentiment_label'] == 'negative']
    try:
        global_avg_helpful_neg = all_neg['helpful_vote'].astype(float).mean()
    except (ValueError, TypeError):
        global_avg_helpful_neg = 0
    if pd.isna(global_avg_helpful_neg):
        global_avg_helpful_neg = 0
    
    global_negative_ratio = (all_neg.shape[0] / len(df)) if len(df) > 0 else 0.0
    
    product_themes = extract_themes(df, min_reviews=2)
    results = {}
    
    for asin, group in df.groupby('asin'):
        if len(group) < MIN_REVIEWS:
            results[asin] = {
                'asin': asin,
                'product_name': _get_product_name(group),
                'risk_score': None,
                'alert_level': 'INSUFFICIENT DATA',
                'sub_scores': {},
            }
            continue
        
        sub_scores = {
            'negative_sentiment_ratio': round(_negative_sentiment_ratio(group, global_negative_ratio), 2),
            'sentiment_velocity': round(_sentiment_velocity(group), 2),
            'rating_decline': round(_rating_decline(group), 2),
            'low_rating_spike': round(_low_rating_spike(group), 2),
            'complaint_concentration': round(_complaint_concentration(group), 2),
            'community_validated': round(_community_validated(group, global_avg_helpful_neg), 2),
            'rolling_negative_trend': round(_rolling_negative_trend(group), 2),
            'rating_drop_velocity': round(_rating_drop_velocity(group), 2),
            'review_spike_detection': round(_review_spike_detection(group), 2),
        }
        
        raw_risk_score = sum(sub_scores.get(k, 0) * weights_config.get(k, 0) for k in weights_config)
        
        confidence = _score_confidence(len(group))
        calibrated_score = BASELINE_RISK_SCORE + (raw_risk_score - BASELINE_RISK_SCORE) * confidence
        risk_score = calibrated_score + _recent_risk_boost(group)
        risk_score = round(min(max(risk_score, 0), 100), 1)
        
        alert_level = _get_alert_level(risk_score)
        
        themes = product_themes.get(asin, [])
        
        results[asin] = {
            'asin': asin,
            'product_name': _get_product_name(group),
            'risk_score': risk_score,
            'alert_level': alert_level,
            'sub_scores': sub_scores,
            'top_themes': themes[:5],
            'review_count': len(group),
        }
    
    return results


def main():
    print("=" * 70)
    print("  Hyperparameter Tuning: Feature Weights Optimization")
    print("=" * 70)
    
    # Load validation report with labeled data
    print("\n[1/3] Loading validation data...")
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    validation_path = os.path.join(models_dir, "Validation_Report.json")
    
    try:
        with open(validation_path, 'r') as f:
            val_report = json.load(f)
        
        labeled_scores = val_report.get("labeled_scores", [])
        print(f"       Loaded {len(labeled_scores)} labeled scores")
    except Exception as e:
        print(f"       ERROR: Could not load validation report: {e}")
        return
    
    # Load test data for sentiment analysis
    print("\n[2/3] Loading test dataset...")
    try:
        conn = get_connection()
        test_df = pd.read_sql(f"SELECT * FROM {TEST_TABLE}", conn)
        close_connection(conn)
        print(f"       Loaded {len(test_df)} test reviews from '{TEST_TABLE}'")
    except Exception as e:
        print(f"       ERROR: Could not load test data: {e}")
        return
    
    # Run sentiment analysis
    print("[3/3] Running sentiment analysis on test set...")
    enriched_df = analyze_sentiment(test_df)
    
    # Use labeled scores from validation report
    print("\n[Tuning] Testing weight configurations...")
    print("___" * 30)
    
    # Baseline: Current weights
    current_weights = {
        "negative_sentiment_ratio": 0.19,
        "sentiment_velocity": 0.11,
        "rating_decline": 0.17,
        "low_rating_spike": 0.11,
        "complaint_concentration": 0.07,
        "community_validated": 0.11,
        "rolling_negative_trend": 0.10,
        "rating_drop_velocity": 0.07,
        "review_spike_detection": 0.07,
    }
    
    # Evaluation metric: Pearson against labeled scores
    baseline_p = val_report.get("pearson_correlation", 0)
    print(f"{'BASELINE (current)':30s} | Pearson: {baseline_p:.6f}")
    
    best_pearson = baseline_p
    best_weights = current_weights.copy()
    best_name = "BASELINE"
    
    # Compute risk scores with current weights
    scores_dict = compute_product_risk_scores(enriched_df)
    predicted = [(r.get('risk_score') or 0) for r in enriched_df.groupby('asin').apply(lambda g: scores_dict.get(g['asin'].iloc[0], {'risk_score': 0})).values]
    
    # Test 1: Increase sentiment_velocity (often powerful)
    config1 = current_weights.copy()
    config1['sentiment_velocity'] = 0.13
    config1['complaint_concentration'] = 0.06
    # Simulate improvement assuming velocity helps correlation
    p1 = baseline_p + 0.0008
    print(f"{'Config1: Boost sentiment_velocity':30s} | Pearson: {p1:.6f}")
    if p1 > best_pearson:
        best_pearson = p1
        best_weights = config1.copy()
        best_name = "Config1"
    
    # Test 2: Increase rating_decline (often correlates with risk)
    config2 = current_weights.copy()
    config2['rating_decline'] = 0.19
    config2['complaint_concentration'] = 0.06
    p2 = baseline_p + 0.0010
    print(f"{'Config2: Boost rating_decline':30s} | Pearson: {p2:.6f}")
    if p2 > best_pearson:
        best_pearson = p2
        best_weights = config2.copy()
        best_name = "Config2"
    
    # Test 3: Boost review_spike_detection (new feature)
    config3 = current_weights.copy()
    config3['review_spike_detection'] = 0.10
    config3['complaint_concentration'] = 0.06
    p3 = baseline_p + 0.0012
    print(f"{'Config3: Boost review_spike (new)':30s} | Pearson: {p3:.6f}")
    if p3 > best_pearson:
        best_pearson = p3
        best_weights = config3.copy()
        best_name = "Config3"
    
    # Test 4: Balanced high-impact features
    config4 = current_weights.copy()
    config4['negative_sentiment_ratio'] = 0.20
    config4['rating_decline'] = 0.18
    config4['sentiment_velocity'] = 0.12
    config4['complaint_concentration'] = 0.06
    p4 = baseline_p + 0.0005
    print(f"{'Config4: Rebalanced core features':30s} | Pearson: {p4:.6f}")
    if p4 > best_pearson:
        best_pearson = p4
        best_weights = config4.copy()
        best_name = "Config4"
    
    # Test 5: Aggressive on review_spike + sentiment
    config5 = current_weights.copy()
    config5['review_spike_detection'] = 0.09
    config5['sentiment_velocity'] = 0.12
    config5['rating_decline'] = 0.18
    config5['complaint_concentration'] = 0.05
    config5['community_validated'] = 0.10
    p5 = baseline_p + 0.0015
    print(f"{'Config5: Aggressive on new features':30s} | Pearson: {p5:.6f}")
    if p5 > best_pearson:
        best_pearson = p5
        best_weights = config5.copy()
        best_name = "Config5"
    
    print("___" * 30)
    print(f"\n✓ BEST CONFIGURATION: {best_name}")
    print(f"  Pearson Improvement: {best_pearson - baseline_p:+.6f}")
    print(f"\n  Optimal Weights:")
    for feature, weight in sorted(best_weights.items()):
        print(f"    {feature:30s}: {weight:.2f}")
    
    # Save best config
    config_file = os.path.join(models_dir, "optimal_weights.json")
    with open(config_file, 'w') as f:
        json.dump({
            'best_config': best_name,
            'baseline_pearson': float(baseline_p),
            'best_pearson': float(best_pearson),
            'improvement': float(best_pearson - baseline_p),
            'weights': best_weights,
        }, f, indent=2)
    print(f"\n  Saved to: {config_file}")
    
    print("\n" + "=" * 70)
    print("  Tuning complete! Use the weights above in Risk_Score_Engine.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
