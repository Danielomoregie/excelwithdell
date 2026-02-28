import pandas as pd
import numpy as np
from Theme_Extractor import extract_themes, classify_review_themes

# ==============================
# CONFIGURATION
# ==============================

WEIGHTS = {
    "negative_sentiment_ratio": 0.25,
    "sentiment_velocity": 0.15,
    "rating_decline": 0.20,
    "low_rating_spike": 0.15,
    "complaint_concentration": 0.10,
    "community_validated": 0.15,
}

MIN_REVIEWS = 3  # Minimum reviews to compute risk score


# ==============================
# SUB-SCORE CALCULATIONS
# ==============================

def _negative_sentiment_ratio(product_df):
    """Sub-score 1: % of reviews that are negative."""
    total = len(product_df)
    if total == 0:
        return 0
    neg_count = (product_df['sentiment_label'] == 'negative').sum()
    return (neg_count / total) * 100


def _sentiment_velocity(product_df):
    """Sub-score 2: Is sentiment getting worse over time?"""
    if len(product_df) < 4:
        return 0
    sorted_df = product_df.sort_values('date')
    midpoint = len(sorted_df) // 2
    older_avg = sorted_df.iloc[:midpoint]['combined_sentiment'].mean()
    recent_avg = sorted_df.iloc[midpoint:]['combined_sentiment'].mean()
    # Positive delta means sentiment declined (older was better)
    delta = older_avg - recent_avg
    # Clamp to [0, 2], scale to 0-100
    return min(max(delta, 0), 2) * 50


def _rating_decline(product_df):
    """Sub-score 3: Recent avg rating vs product overall average_rating."""
    if len(product_df) < 4:
        return 0
    sorted_df = product_df.sort_values('date')
    recent_quarter = sorted_df.tail(max(len(sorted_df) // 4, 1))
    recent_avg = recent_quarter['rating'].mean()

    # Use the product's overall average_rating from the dataset
    overall_avg = product_df['average_rating'].iloc[0]
    try:
        overall_avg = float(overall_avg)
    except (ValueError, TypeError):
        overall_avg = product_df['rating'].mean()

    gap = overall_avg - recent_avg
    # Clamp to [0, 3], scale to 0-100
    return min(max(gap, 0), 3) * (100 / 3)


def _low_rating_spike(product_df):
    """Sub-score 4: Surge in 1-2 star reviews recently vs historical."""
    if 'date' not in product_df.columns or len(product_df) < 6:
        return 0

    sorted_df = product_df.sort_values('date')
    sorted_df['year_month'] = sorted_df['date'].dt.to_period('M')

    all_months = sorted_df['year_month'].unique()
    if len(all_months) < 4:
        return 0

    # Last 3 months vs everything before
    recent_months = all_months[-3:]
    recent = sorted_df[sorted_df['year_month'].isin(recent_months)]
    historical = sorted_df[~sorted_df['year_month'].isin(recent_months)]

    recent_low_count = (recent['rating'] <= 2).sum()
    recent_month_count = len(recent_months)
    recent_rate = recent_low_count / recent_month_count if recent_month_count > 0 else 0

    hist_months = historical['year_month'].nunique()
    hist_low_count = (historical['rating'] <= 2).sum()
    hist_rate = hist_low_count / hist_months if hist_months > 0 else 0

    if hist_rate > 0:
        spike_ratio = recent_rate / hist_rate
    else:
        spike_ratio = 1 if recent_low_count > 0 else 0

    # Clamp [0, 5], subtract baseline of 1, scale to 0-100
    return min(max(spike_ratio - 1, 0), 4) * 25


def _complaint_concentration(product_df):
    """Sub-score 5: Does one complaint theme dominate negative reviews?"""
    neg_df = product_df[product_df['sentiment_label'] == 'negative']
    if len(neg_df) < 2:
        return 0

    theme_counts = {}
    for _, row in neg_df.iterrows():
        themes = classify_review_themes(row.get('text_cleaned', ''))
        for theme in themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    if not theme_counts:
        return 0

    top_count = max(theme_counts.values())
    top_share = top_count / len(neg_df)
    return top_share * 100


def _community_validated(product_df, global_avg_helpful_neg):
    """Sub-score 6: Are negative reviews getting more helpful_votes?"""
    neg_df = product_df[product_df['sentiment_label'] == 'negative']
    if len(neg_df) == 0 or global_avg_helpful_neg <= 0:
        return 0

    try:
        avg_helpful_neg = neg_df['helpful_vote'].astype(float).mean()
    except (ValueError, TypeError):
        return 0

    ratio = avg_helpful_neg / global_avg_helpful_neg
    # Clamp [0, 5], subtract baseline of 1, scale to 0-100
    return min(max(ratio - 1, 0), 4) * 25


# ==============================
# COMPOSITE RISK SCORE
# ==============================

def compute_product_risk_scores(enriched_df):
    """
    Compute composite risk scores for all products.

    Args:
        enriched_df: DataFrame with sentiment columns from Sentiment_Analyzer

    Returns:
        dict: {asin: {risk_score, sub_scores, alert_level, product_name, ...}}
    """
    # Pre-compute global stats
    all_neg = enriched_df[enriched_df['sentiment_label'] == 'negative']
    try:
        global_avg_helpful_neg = all_neg['helpful_vote'].astype(float).mean()
    except (ValueError, TypeError):
        global_avg_helpful_neg = 0
    if pd.isna(global_avg_helpful_neg):
        global_avg_helpful_neg = 0

    # Extract themes for all products
    product_themes = extract_themes(enriched_df, min_reviews=2)

    results = {}

    for asin, group in enriched_df.groupby('asin'):
        if len(group) < MIN_REVIEWS:
            results[asin] = {
                'asin': asin,
                'product_name': _get_product_name(group),
                'risk_score': None,
                'alert_level': 'INSUFFICIENT DATA',
                'sub_scores': {},
                'top_themes': [],
                'review_count': len(group),
                'average_rating': _safe_float(group['average_rating'].iloc[0]),
                'price': _safe_float(group['price'].iloc[0]) if 'price' in group.columns else None,
            }
            continue

        sub_scores = {
            'negative_sentiment_ratio': round(_negative_sentiment_ratio(group), 2),
            'sentiment_velocity': round(_sentiment_velocity(group), 2),
            'rating_decline': round(_rating_decline(group), 2),
            'low_rating_spike': round(_low_rating_spike(group), 2),
            'complaint_concentration': round(_complaint_concentration(group), 2),
            'community_validated': round(_community_validated(group, global_avg_helpful_neg), 2),
        }

        risk_score = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
        risk_score = round(min(max(risk_score, 0), 100), 1)

        alert_level = _get_alert_level(risk_score)

        themes = product_themes.get(asin, [])

        results[asin] = {
            'asin': asin,
            'product_name': _get_product_name(group),
            'risk_score': risk_score,
            'alert_level': alert_level,
            'sub_scores': sub_scores,
            'top_themes': themes[:5],  # Top 5 themes
            'review_count': len(group),
            'average_rating': _safe_float(group['average_rating'].iloc[0]),
            'price': _safe_float(group['price'].iloc[0]) if 'price' in group.columns else None,
        }

    return results


def compute_risk_trends(enriched_df, window_size='3M'):
    """
    Compute risk-relevant metrics over sliding time windows for trend charts.
    Returns list of dicts with monthly aggregations.
    """
    if 'date' not in enriched_df.columns:
        return []

    df = enriched_df.copy()
    df['year_month'] = df['date'].dt.to_period('M')

    trends = []
    for period, group in df.groupby('year_month'):
        total = len(group)
        neg_count = (group['sentiment_label'] == 'negative').sum()
        trends.append({
            'month': str(period),
            'avg_sentiment': round(group['combined_sentiment'].mean(), 4),
            'negative_ratio': round(neg_count / total, 4) if total > 0 else 0,
            'review_count': total,
            'avg_rating': round(group['rating'].astype(float).mean(), 2),
        })

    return sorted(trends, key=lambda x: x['month'])


def generate_alerts(risk_results):
    """
    Filter products with CRITICAL or HIGH alert levels.
    Returns sorted list of alerts.
    """
    alerts = []
    for asin, data in risk_results.items():
        if data['alert_level'] in ('CRITICAL', 'HIGH'):
            top_theme_names = [t[0] for t in data.get('top_themes', [])][:3]
            alerts.append({
                'asin': asin,
                'product_name': data['product_name'],
                'risk_score': data['risk_score'],
                'alert_level': data['alert_level'],
                'top_themes': top_theme_names,
                'review_count': data['review_count'],
            })
    return sorted(alerts, key=lambda x: x['risk_score'] or 0, reverse=True)


# ==============================
# HELPERS
# ==============================

def _get_alert_level(risk_score):
    if risk_score >= 75:
        return "CRITICAL"
    elif risk_score >= 50:
        return "HIGH"
    elif risk_score >= 25:
        return "MODERATE"
    else:
        return "LOW"


def _get_product_name(group):
    name = group['title_y'].iloc[0]
    if pd.isna(name):
        return "Unknown Product"
    name = str(name)
    if len(name) > 80:
        return name[:77] + "..."
    return name


def _safe_float(val):
    try:
        f = float(val)
        return f if not pd.isna(f) else None
    except (ValueError, TypeError):
        return None
