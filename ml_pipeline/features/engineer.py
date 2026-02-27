"""
Feature engineering at ASIN x Month level.
Creates volume, quality, text risk, time, and optional support ticket signals.
"""
import pandas as pd
import numpy as np
import re
from typing import Optional

# Term lists for text risk signals
DEFECT_TERMS = [
    "defect", "broken", "malfunction", "faulty", "doesn't work", "won't work",
    "dead on arrival", "doa", "failed", "failure", "overheating", "crashed",
    "screen crack", "keyboard broken", "warranty", "replace", "refund"
]
RETURN_TERMS = ["return", "refund", "sent back", "send back", "money back"]
SAFETY_TERMS = ["fire", "burn", "explode", "overheat", "smoke", "spark", "safety"]


def _safe_divide(a: np.ndarray, b: np.ndarray, fill: float = 0.0) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(b > 0, a / b, fill)
    return np.nan_to_num(out, nan=fill, posinf=fill, neginf=fill)


def _text_risk_score(text_series: pd.Series, terms: list) -> pd.Series:
    """Compute rate of reviews containing any of the given terms."""
    if text_series.isna().all():
        return pd.Series(0.0, index=text_series.index)
    pattern = "|".join(re.escape(t) for t in terms)
    return text_series.fillna("").str.lower().str.contains(pattern, regex=True).astype(float)


def aggregate_to_asin_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw reviews to ASIN x Month level.
    """
    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    hv_col = "helpful_vote" if "helpful_vote" in df.columns else "avg_helpful_votes"
    if hv_col not in df.columns:
        df["helpful_vote"] = 0
        hv_col = "helpful_vote"

    # Volume + quality signals (single groupby)
    vol = df.groupby(["asin", "month"]).agg(
        review_count=("rating", "count"),
        avg_helpful_votes=(hv_col, "mean"),
    ).reset_index()

    qual = df.groupby(["asin", "month"]).agg(
        avg_rating=("rating", "mean"),
        pct_1star=("rating", lambda x: float((x == 1).mean())),
        pct_2star=("rating", lambda x: float((x == 2).mean())),
    ).reset_index()

    # Text risk signals (per review, then aggregate to month)
    df["defect_flag"] = _text_risk_score(df["text"] if "text" in df.columns else pd.Series(""), DEFECT_TERMS)
    df["return_flag"] = _text_risk_score(df["text"] if "text" in df.columns else pd.Series(""), RETURN_TERMS)
    df["safety_flag"] = _text_risk_score(df["text"] if "text" in df.columns else pd.Series(""), SAFETY_TERMS)

    text_agg = df.groupby(["asin", "month"]).agg(
        defect_terms_rate=("defect_flag", "mean"),
        return_terms_rate=("return_flag", "mean"),
        safety_terms_rate=("safety_flag", "mean"),
    ).reset_index()

    # Simple negative sentiment: % of 1–2 star with "not" or "bad" in text
    txt = df["text"].fillna("") if "text" in df.columns else pd.Series("", index=df.index)
    df["neg_sent"] = ((df["rating"] <= 2) & (txt.str.lower().str.contains(r"(?:not|bad|terrible|awful|horrible)", regex=True))).astype(float)
    neg_sent = df.groupby(["asin", "month"])["neg_sent"].mean().reset_index()
    neg_sent = neg_sent.rename(columns={"neg_sent": "negative_sentiment_score"})

    # Merge
    agg = vol.merge(qual, on=["asin", "month"], how="outer")
    agg = agg.merge(text_agg, on=["asin", "month"], how="outer")
    agg = agg.merge(neg_sent, on=["asin", "month"], how="outer")

    agg = agg.fillna(0)

    # Sort for rolling
    agg["month_dt"] = pd.to_datetime(agg["month"] + "-01")
    agg = agg.sort_values(["asin", "month_dt"]).reset_index(drop=True)

    return agg


def add_rolling_features(agg: pd.DataFrame, windows: list = [1, 3]) -> pd.DataFrame:
    """Add lag and rolling features. No look-ahead."""
    agg = agg.copy()
    for w in windows:
        agg[f"avg_rating_roll{w}"] = agg.groupby("asin")["avg_rating"].transform(
            lambda x: x.shift(1).rolling(w, min_periods=1).mean()
        )
        agg[f"defect_terms_roll{w}"] = agg.groupby("asin")["defect_terms_rate"].transform(
            lambda x: x.shift(1).rolling(w, min_periods=1).mean()
        )

    def _slope(y):
        if len(y) < 2:
            return 0.0
        try:
            return float(np.polyfit(range(len(y)), y, 1)[0])
        except Exception:
            return 0.0
    agg["rating_trend"] = agg.groupby("asin")["avg_rating"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=2).apply(_slope, raw=True)
    )
    agg["rating_trend"] = agg["rating_trend"].fillna(0)

    agg["defect_1m_lag"] = agg.groupby("asin")["defect_terms_rate"].shift(1).fillna(0)
    agg["rating_1m_lag"] = agg.groupby("asin")["avg_rating"].shift(1).fillna(agg["avg_rating"].mean())
    agg["rolling_volatility"] = agg.groupby("asin")["avg_rating"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=2).std().fillna(0)
    )

    return agg


def add_pct_verified(agg: pd.DataFrame) -> pd.DataFrame:
    """Add pct_verified if not present (default 0)."""
    if "pct_verified" not in agg.columns:
        agg["pct_verified"] = 0.0
    return agg


def build_features(df: pd.DataFrame, support_tickets: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Full feature pipeline: aggregate -> rolling -> optional tickets.
    """
    agg = aggregate_to_asin_month(df)
    agg = add_rolling_features(agg)
    agg = add_pct_verified(agg)

    if support_tickets is not None and len(support_tickets) > 0:
        st = support_tickets.copy()
        if "month" not in st.columns and "date" in st.columns:
            st["month"] = pd.to_datetime(st["date"]).dt.to_period("M").astype(str)
        # If already aggregated (ticket_count, high_severity_rate, resolution_time_avg exist)
        if "ticket_count" in st.columns and "high_severity_rate" in st.columns:
            ticket_agg = st[["asin", "month", "ticket_count", "high_severity_rate", "resolution_time_avg"]].drop_duplicates(["asin", "month"])
        else:
            ticket_agg = st.groupby(["asin", "month"]).agg(
                ticket_count=("ticket_id" if "ticket_id" in st.columns else st.columns[0], "count"),
                high_severity_rate=("severity" if "severity" in st.columns else st.columns[1], lambda x: float((x == "high").mean())),
                resolution_time_avg=("resolution_hours" if "resolution_hours" in st.columns else st.columns[-1], "mean"),
            ).reset_index()
        agg = agg.merge(ticket_agg, on=["asin", "month"], how="left")
        agg["ticket_count"] = agg["ticket_count"].fillna(0)
        agg["high_severity_rate"] = agg["high_severity_rate"].fillna(0)
        agg["resolution_time_avg"] = agg["resolution_time_avg"].fillna(0)

    return agg
