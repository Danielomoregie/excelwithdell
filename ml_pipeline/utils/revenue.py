"""
Revenue-weighted risk scoring and exposure estimation.
"""
import pandas as pd
import numpy as np
from ml_pipeline.utils.config import (
    ANNUAL_REVENUE_B, NUM_PRODUCTS, RECOVERY_RATE_MIN, RECOVERY_RATE_MAX,
    MONTHS_EARLY_DETECTION
)


def add_revenue_exposure(
    df: pd.DataFrame,
    risk_prob_col: str = "risk_probability",
) -> pd.DataFrame:
    """
    Add revenue exposure and expected revenue saved columns.

    Monthly revenue per product = (2.8B / 12) / 40
    If risk flagged 4 months earlier: Revenue Saved ≈ monthly_revenue × 4 × recovery_rate (0.3–0.5)
    """
    df = df.copy()
    monthly_revenue_per_product = (ANNUAL_REVENUE_B * 1e9 / 12) / NUM_PRODUCTS

    # Expected revenue exposure (probability-weighted)
    df["expected_revenue_exposure"] = (
        df[risk_prob_col] * monthly_revenue_per_product * MONTHS_EARLY_DETECTION
    )

    # Expected revenue saved (if action taken early)
    recovery_rate_avg = (RECOVERY_RATE_MIN + RECOVERY_RATE_MAX) / 2
    df["expected_revenue_saved"] = (
        df[risk_prob_col] * monthly_revenue_per_product * MONTHS_EARLY_DETECTION * recovery_rate_avg
    )

    return df


def compute_revenue_summary(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue impact by month and product."""
    if "expected_revenue_exposure" not in predictions_df.columns:
        return pd.DataFrame()
    summary = predictions_df.groupby("month").agg(
        total_exposure=("expected_revenue_exposure", "sum"),
        total_saved=("expected_revenue_saved", "sum"),
        risk_count=("risk_event", "sum"),
    ).reset_index()
    return summary
