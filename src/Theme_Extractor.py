from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import pandas as pd

# ==============================
# COMPLAINT CATEGORIES (Laptop-Specific)
# ==============================

COMPLAINT_CATEGORIES = {
    "overheating": ["hot", "heat", "overheat", "thermal", "fan", "temperature", "burn", "warm"],
    "battery": ["battery", "charge", "charging", "power supply", "drain", "dies", "power cord",
                "adapter", "ac adapter"],
    "screen": ["screen", "display", "flicker", "dead pixel", "dim", "bright", "crack",
               "monitor", "lcd", "resolution", "backlight"],
    "performance": ["slow", "lag", "freeze", "crash", "hang", "boot", "startup", "speed",
                    "loading", "memory", "ram"],
    "keyboard": ["keyboard", "key", "typing", "trackpad", "touchpad", "mouse pad"],
    "build_quality": ["cheap", "plastic", "broken", "crack", "hinge", "flimsy", "build",
                      "quality", "fragile", "heavy", "weight"],
    "software": ["driver", "update", "windows", "bios", "bloatware", "software", "os",
                 "install", "blue screen", "bsod"],
    "connectivity": ["wifi", "bluetooth", "usb", "port", "adapter", "network", "ethernet",
                     "wireless", "connection", "internet"],
    "customer_service": ["support", "warranty", "return", "refund", "service", "replace",
                         "dell", "fusiontech", "repair"],
    "value": ["price", "expensive", "overpriced", "money", "worth", "cost", "value",
              "refurbished"],
}


# ==============================
# THEME EXTRACTION
# ==============================

def classify_review_themes(text):
    """
    Match a single review text against complaint categories.
    Returns list of matching theme names.
    """
    if not text or pd.isna(text):
        return []
    text_lower = str(text).lower()
    matched = []
    for theme, keywords in COMPLAINT_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(theme)
    return matched


def extract_themes(df, min_reviews=3):
    """
    For each product with negative reviews, extract complaint themes.

    Args:
        df: DataFrame with 'asin', 'text_cleaned', 'sentiment_label' columns
        min_reviews: minimum negative reviews to compute themes

    Returns:
        dict: {asin: [("theme_name", frequency_ratio), ...]} sorted by frequency
    """
    negative_df = df[df['sentiment_label'] == 'negative'].copy()
    product_themes = {}

    for asin, group in negative_df.groupby('asin'):
        if len(group) < min_reviews:
            continue

        # Count themes across all negative reviews for this product
        theme_counts = {}
        total_neg = len(group)

        for _, row in group.iterrows():
            themes = classify_review_themes(row.get('text_cleaned', ''))
            for theme in themes:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Convert to sorted list of (theme, frequency_ratio)
        theme_list = [
            (theme, round(count / total_neg, 4))
            for theme, count in theme_counts.items()
        ]
        theme_list.sort(key=lambda x: x[1], reverse=True)
        product_themes[asin] = theme_list

    return product_themes


def train_tfidf_model(df):
    """
    Train TF-IDF vectorizer on negative review texts.
    Returns the fitted vectorizer and feature names.
    """
    negative_texts = df[df['sentiment_label'] == 'negative']['text_cleaned'].dropna()
    negative_texts = negative_texts[negative_texts.str.len() > 10]

    if len(negative_texts) < 5:
        return None, []

    vectorizer = TfidfVectorizer(
        max_features=3000,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
    )
    tfidf_matrix = vectorizer.fit_transform(negative_texts)
    feature_names = vectorizer.get_feature_names_out()

    return vectorizer, feature_names


def get_top_tfidf_terms(vectorizer, texts, top_n=20):
    """
    Get the top TF-IDF terms across a set of texts.
    Returns list of (term, avg_tfidf_score).
    """
    if vectorizer is None or len(texts) == 0:
        return []
    tfidf_matrix = vectorizer.transform(texts)
    avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
    feature_names = vectorizer.get_feature_names_out()

    top_indices = avg_scores.argsort()[::-1][:top_n]
    return [(feature_names[i], round(float(avg_scores[i]), 4)) for i in top_indices]


def get_global_theme_counts(df):
    """
    Count complaint themes across all negative reviews globally.
    Returns dict: {theme: count} sorted descending.
    """
    negative_df = df[df['sentiment_label'] == 'negative']
    theme_counts = {}

    for _, row in negative_df.iterrows():
        themes = classify_review_themes(row.get('text_cleaned', ''))
        for theme in themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    return dict(sorted(theme_counts.items(), key=lambda x: x[1], reverse=True))


def get_emerging_themes(df, recent_months=3):
    """
    Compare themes in the most recent N months vs. historical.
    Returns themes whose frequency has notably increased.
    """
    if 'date' not in df.columns:
        return {}

    df_sorted = df.sort_values('date')
    negative_df = df_sorted[df_sorted['sentiment_label'] == 'negative'].copy()

    if negative_df.empty:
        return {}

    negative_df['year_month'] = negative_df['date'].dt.to_period('M')
    all_months = negative_df['year_month'].unique()

    if len(all_months) < recent_months + 1:
        return {}

    cutoff = all_months[-recent_months]
    recent = negative_df[negative_df['year_month'] >= cutoff]
    historical = negative_df[negative_df['year_month'] < cutoff]

    if historical.empty or recent.empty:
        return {}

    # Theme rates
    def theme_rate(subset):
        counts = {}
        total = len(subset)
        for _, row in subset.iterrows():
            for theme in classify_review_themes(row.get('text_cleaned', '')):
                counts[theme] = counts.get(theme, 0) + 1
        return {t: c / total for t, c in counts.items()} if total > 0 else {}

    hist_rates = theme_rate(historical)
    recent_rates = theme_rate(recent)

    emerging = {}
    for theme, rate in recent_rates.items():
        hist_rate = hist_rates.get(theme, 0)
        if hist_rate > 0:
            change = (rate - hist_rate) / hist_rate
        else:
            change = 1.0 if rate > 0 else 0
        if change > 0.2:  # 20% increase threshold
            emerging[theme] = round(change, 4)

    return dict(sorted(emerging.items(), key=lambda x: x[1], reverse=True))
