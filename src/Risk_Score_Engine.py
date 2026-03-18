import pandas as pd
import numpy as np
from Theme_Extractor import extract_themes, classify_review_themes

# ==============================
# CONFIGURATION
# ==============================

WEIGHTS = {
    "negative_sentiment_ratio": 0.20,
    "sentiment_velocity": 0.13,
    "rating_decline": 0.19,
    "low_rating_spike": 0.10,
    "complaint_concentration": 0.06,
    "community_validated": 0.11,
    "rolling_negative_trend": 0.10,
    "rating_drop_velocity": 0.06,
    "review_spike_detection": 0.05,
}

ALERT_THRESHOLDS = {
    "critical": 75,
    "high": 50,
    "moderate": 25,
}

MIN_REVIEWS = 3  # Minimum reviews to compute risk score

# Temporal weighting: recent reviews more important than old ones
# Full weight for reviews in last 1 month, exponential decay beyond
TEMPORAL_DECAY_DAYS = 30  # 1 month in days
TEMPORAL_DECAY_RATE = 0.5  # Half-life of 1 month; older reviews decay exponentially

# Use light Bayesian smoothing and confidence calibration so products
# with sparse reviews do not swing to extreme scores too easily.
NEGATIVE_RATIO_PRIOR_STRENGTH = 8
LOW_RATING_PRIOR_STRENGTH = 8
CONFIDENCE_FULL_AT_REVIEWS = 25
BASELINE_RISK_SCORE = 35.0

# ==============================
# SUB-SCORE CALCULATIONS
# ==============================

def _apply_temporal_decay(product_df):
    """
    Weight recent reviews more heavily than old ones.
    Returns dataframe with added 'temporal_weight' column.
    Reviews from last 2 years get full weight, older ones decayed exponentially.
    """
    if 'date' not in product_df.columns or product_df.empty:
        return product_df.copy()
    
    df = product_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Remove rows with invalid dates
    df = df[pd.notna(df['date'])]
    if df.empty:
        product_df['temporal_weight'] = 1.0
        return product_df
    
    max_date = df['date'].max()
    if pd.isna(max_date):
        product_df['temporal_weight'] = 1.0
        return product_df
    
    # Calculate age in days
    df['age_days'] = (max_date - df['date']).dt.days

    # Full weight for last 1 month (30 days), then exponential decay
    full_weight_days = TEMPORAL_DECAY_DAYS
    decay_mask = df['age_days'] > full_weight_days
    df['temporal_weight'] = 1.0
    df.loc[decay_mask, 'temporal_weight'] = np.power(
        TEMPORAL_DECAY_RATE, (df.loc[decay_mask, 'age_days'] - full_weight_days) / TEMPORAL_DECAY_DAYS
    )
    return df


# ==============================
# SUB-SCORE CALCULATIONS
# ==============================

def _negative_sentiment_ratio(product_df, global_negative_ratio):
    """Sub-score 1: % of reviews that are negative (weighted by temporal recency)."""
    if product_df.empty:
        return 0
    
    # Apply temporal decay to weight recent reviews more heavily
    df_weighted = _apply_temporal_decay(product_df)
    
    weighted_total = df_weighted['temporal_weight'].sum()
    if weighted_total == 0:
        return 0
    
    neg_mask = df_weighted['sentiment_label'] == 'negative'
    weighted_neg_count = df_weighted[neg_mask]['temporal_weight'].sum()

    prior_neg = global_negative_ratio * NEGATIVE_RATIO_PRIOR_STRENGTH
    smoothed_ratio = (weighted_neg_count + prior_neg) / (weighted_total + NEGATIVE_RATIO_PRIOR_STRENGTH)
    return smoothed_ratio * 100


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

    if historical.empty:
        return 0

    recent_low_count = (recent['rating'] <= 2).sum()
    recent_total = len(recent)

    hist_low_count = (historical['rating'] <= 2).sum()
    hist_total = len(historical)

    if recent_total == 0 or hist_total == 0:
        return 0

    # Smoothed rates by review volume, not by month count.
    recent_rate = (recent_low_count + LOW_RATING_PRIOR_STRENGTH * 0.1) / (recent_total + LOW_RATING_PRIOR_STRENGTH)
    hist_rate = (hist_low_count + LOW_RATING_PRIOR_STRENGTH * 0.1) / (hist_total + LOW_RATING_PRIOR_STRENGTH)

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


def _recent_risk_boost(product_df):
    """Add a small boost when the latest window shows concentrated deterioration."""
    if 'date' not in product_df.columns or product_df.empty:
        return 0.0

    dated = product_df.copy()
    dated = dated[pd.notna(dated['date'])]
    if dated.empty:
        return 0.0

    latest_date = dated['date'].max()
    if pd.isna(latest_date):
        return 0.0

    cutoff = latest_date - pd.Timedelta(days=90)
    recent = dated[dated['date'] >= cutoff]
    if recent.empty:
        return 0.0

    recent_neg_ratio = (recent['sentiment_label'] == 'negative').mean()
    recent_low_ratio = (recent['rating'].astype(float) <= 2).mean()
    recent_sentiment = float(recent['combined_sentiment'].mean())

    neg_component = min(max((recent_neg_ratio - 0.35) / 0.45, 0), 1) * 5.0
    low_component = min(max((recent_low_ratio - 0.20) / 0.50, 0), 1) * 4.0
    sentiment_component = min(max((-recent_sentiment - 0.05) / 0.45, 0), 1) * 3.0

    return round(neg_component + low_component + sentiment_component, 2)


def _score_confidence(review_count):
    """Confidence from 0-1, increasing smoothly with sample size."""
    if review_count <= 0:
        return 0.0
    return min(np.log1p(review_count) / np.log1p(CONFIDENCE_FULL_AT_REVIEWS), 1.0)


def _rolling_negative_trend(product_df):
    """
    Sub-score 7: Detect if negative review ratio is accelerating.
    Compares recent rolling window to historical rolling window.
    Returns 0-100 score.
    """
    if 'date' not in product_df.columns or len(product_df) < 8:
        return 0.0
    
    dated = product_df.copy()
    dated = dated[pd.notna(dated['date'])].sort_values('date')
    if len(dated) < 8:
        return 0.0
    
    # Split into 2-month rolling windows
    dated['year_month'] = dated['date'].dt.to_period('M')
    monthly_stats = []
    
    for period, group in dated.groupby('year_month'):
        neg_ratio = (group['sentiment_label'] == 'negative').mean()
        monthly_stats.append(neg_ratio)
    
    if len(monthly_stats) < 4:
        return 0.0
    
    # Compare recent half to historical half
    midpoint = len(monthly_stats) // 2
    hist_avg = np.mean(monthly_stats[:midpoint])
    recent_avg = np.mean(monthly_stats[midpoint:])
    
    acceleration = (recent_avg - hist_avg) / (hist_avg + 0.01)  # Avoid division by zero
    # Clamp [0, 3], scale to 0-100
    return min(max(acceleration * 33, 0), 100)


def _rating_drop_velocity(product_df):
    """
    Sub-score 8: Detect if product ratings are DROPPING (not just low).
    High for products going downhill, neutral for stable products.
    Returns 0-100 score.
    """
    if 'date' not in product_df.columns or len(product_df) < 6:
        return 0.0
    
    dated = product_df.copy()
    dated = dated[pd.notna(dated['date'])].sort_values('date')
    if len(dated) < 6:
        return 0.0
    
    # Split into two halves by time
    midpoint = len(dated) // 2
    hist_avg = dated.iloc[:midpoint]['rating'].astype(float).mean()
    recent_avg = dated.iloc[midpoint:]['rating'].astype(float).mean()
    
    drop = hist_avg - recent_avg
    # Clamp [0, 3], scale to 0-100
    return min(max(drop * 33, 0), 100)


def _review_spike_detection(product_df):
    """
    Sub-score 9: Detect sudden spike in review volume (often precedes risk).
    Returns 0-100 score.
    """
    if 'date' not in product_df.columns or len(product_df) < 8:
        return 0.0
    
    dated = product_df.copy()
    dated = dated[pd.notna(dated['date'])].sort_values('date')
    if len(dated) < 8:
        return 0.0
    
    # Count reviews per month
    dated['year_month'] = dated['date'].dt.to_period('M')
    monthly_counts = [len(group) for _, group in dated.groupby('year_month')]
    
    if len(monthly_counts) < 3:
        return 0.0
    
    avg_count = np.mean(monthly_counts)
    recent_count = monthly_counts[-1]
    
    spike_ratio = recent_count / (avg_count + 1)  # Avoid division by zero
    # Clamp [0, 5], subtract 1, scale to 0-100
    return min(max((spike_ratio - 1) * 20, 0), 100)


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

    global_negative_ratio = (all_neg.shape[0] / len(enriched_df)) if len(enriched_df) > 0 else 0.0

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

        raw_risk_score = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)

        # Calibrate volatility for low-sample products and add a bounded recency signal.
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
            'top_themes': themes[:5],  # Top 5 themes
            'review_count': len(group),
            'average_rating': _safe_float(group['average_rating'].iloc[0]),
            'price': _safe_float(group['price'].iloc[0]) if 'price' in group.columns else None,
        }

    return results


def compute_risk_trends(enriched_df, window_size='3M'):
    """
    Compute risk-relevant metrics over sliding 3-month windows for trend charts.
    Returns list of dicts with rolling 3-month aggregations.
    """
    if 'date' not in enriched_df.columns:
        return []

    df = enriched_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.sort_values('date')
    df = df[pd.notna(df['date'])]

    # Set date as index for rolling
    df = df.set_index('date')

    # Resample monthly, then apply 3-month rolling window
    monthly = df.resample('M').agg({
        'combined_sentiment': 'mean',
        'sentiment_label': lambda x: (x == 'negative').sum(),
        'rating': 'mean',
        'asin': 'count'
    }).rename(columns={'asin': 'review_count'})

    # Calculate unhappy review %
    monthly['negative_ratio'] = monthly['sentiment_label'] / monthly['review_count']
    monthly['avg_sentiment'] = monthly['combined_sentiment']

    # 3-month rolling averages
    monthly['avg_sentiment_3mo'] = monthly['avg_sentiment'].rolling(window=3, min_periods=1).mean()
    monthly['negative_ratio_3mo'] = monthly['negative_ratio'].rolling(window=3, min_periods=1).mean()

    # Build trend list for all months in range
    trends = []
    for idx, row in monthly.iterrows():
        trends.append({
            'month': idx.strftime('%Y-%m'),
            'avg_sentiment_3mo': round(row['avg_sentiment_3mo'], 4) if not pd.isna(row['avg_sentiment_3mo']) else None,
            'negative_ratio_3mo': round(row['negative_ratio_3mo'], 4) if not pd.isna(row['negative_ratio_3mo']) else None,
            'review_count': int(row['review_count']) if not pd.isna(row['review_count']) else 0,
        })

    return trends


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
    if risk_score >= ALERT_THRESHOLDS["critical"]:
        return "CRITICAL"
    elif risk_score >= ALERT_THRESHOLDS["high"]:
        return "HIGH"
    elif risk_score >= ALERT_THRESHOLDS["moderate"]:
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
