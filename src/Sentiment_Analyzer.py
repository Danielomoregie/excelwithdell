import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import pandas as pd
import re

# Download VADER lexicon on first import
nltk.download('vader_lexicon', quiet=True)

# ==============================
# TEXT CLEANING
# ==============================

def clean_review_text(text):
    """Remove HTML tags, entities, and normalize whitespace."""
    if pd.isna(text) or str(text).strip() == "":
        return ""
    text = str(text)
    text = re.sub(r'<[^>]+>', ' ', text)        # strip HTML tags
    text = re.sub(r'&#\d+;', '', text)           # strip HTML entities like &#34;
    text = re.sub(r'&\w+;', '', text)            # strip named entities like &amp;
    text = re.sub(r'\s+', ' ', text).strip()     # normalize whitespace
    return text


# ==============================
# SENTIMENT ANALYSIS
# ==============================

def analyze_sentiment(df):
    """
    Analyze sentiment for a DataFrame of reviews.

    Expects columns: 'text', 'title_x'
    Returns DataFrame with added columns:
      - text_cleaned
      - text_sentiment (VADER compound score)
      - title_sentiment (VADER compound score)
      - combined_sentiment (weighted average)
      - sentiment_label ('positive', 'negative', 'neutral')
    """
    sia = SentimentIntensityAnalyzer()
    df = df.copy()

    # Clean the review text
    df['text_cleaned'] = df['text'].apply(clean_review_text)

    # Sentiment on review body
    df['text_sentiment'] = df['text_cleaned'].apply(
        lambda t: sia.polarity_scores(t)['compound'] if t else 0.0
    )

    # Sentiment on review title
    df['title_sentiment'] = df['title_x'].apply(
        lambda t: sia.polarity_scores(str(t))['compound'] if pd.notna(t) else 0.0
    )

    # Weighted combination: body matters more, but title carries signal
    # For very short or empty text, lean more on title
    def combined_score(row):
        text_len = len(row['text_cleaned'].split()) if row['text_cleaned'] else 0
        if text_len < 5:
            return 0.4 * row['text_sentiment'] + 0.6 * row['title_sentiment']
        return 0.7 * row['text_sentiment'] + 0.3 * row['title_sentiment']

    df['combined_sentiment'] = df.apply(combined_score, axis=1)

    # Classification label
    df['sentiment_label'] = df['combined_sentiment'].apply(
        lambda s: 'positive' if s >= 0.05 else ('negative' if s <= -0.05 else 'neutral')
    )

    return df


def get_sentiment_summary(df, asin):
    """Return sentiment statistics for a single product."""
    product_df = df[df['asin'] == asin].copy()
    if product_df.empty:
        return None

    total = len(product_df)
    neg_count = (product_df['sentiment_label'] == 'negative').sum()
    pos_count = (product_df['sentiment_label'] == 'positive').sum()
    neu_count = (product_df['sentiment_label'] == 'neutral').sum()

    return {
        'asin': asin,
        'total_reviews': total,
        'positive_count': int(pos_count),
        'negative_count': int(neg_count),
        'neutral_count': int(neu_count),
        'negative_ratio': round(neg_count / total, 4) if total > 0 else 0,
        'avg_sentiment': round(product_df['combined_sentiment'].mean(), 4),
        'sentiment_std': round(product_df['combined_sentiment'].std(), 4) if total > 1 else 0,
    }
