"""
Label definition: risk_event = 1 if NEXT MONTH meets risk criteria.
Prevents data leakage by using future data only for labels.
"""
import pandas as pd
import numpy as np
from ml_pipeline.utils.config import PCT_1STAR_THRESHOLD, RATING_DROP_THRESHOLD


def compute_labels(agg: pd.DataFrame) -> pd.DataFrame:
    """
    Define binary risk_event = 1 if NEXT MONTH:
    - pct_1star >= 35%
    OR
    - avg_rating drops >= 0.7 from 3-month rolling mean
    OR
    - defect_terms_rate doubles relative to rolling baseline

    Uses shifted (next month) values for labels - no leakage.
    """
    agg = agg.copy()
    agg = agg.sort_values(["asin", "month_dt"]).reset_index(drop=True)

    # Next month's values (the month we are predicting)
    agg["pct_1star_next"] = agg.groupby("asin")["pct_1star"].shift(-1)
    agg["avg_rating_next"] = agg.groupby("asin")["avg_rating"].shift(-1)
    agg["defect_terms_next"] = agg.groupby("asin")["defect_terms_rate"].shift(-1)

    # Rolling baseline for defect (3m) and rating (3m mean)
    agg["defect_roll3_baseline"] = agg.groupby("asin")["defect_terms_rate"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    agg["rating_roll3_mean"] = agg.groupby("asin")["avg_rating"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    # Risk conditions (based on NEXT month)
    cond_1star = agg["pct_1star_next"] >= PCT_1STAR_THRESHOLD
    cond_rating_drop = (
        (agg["rating_roll3_mean"] - agg["avg_rating_next"]) >= RATING_DROP_THRESHOLD
    )
    cond_defect = (
        agg["defect_roll3_baseline"] > 0
    ) & (
        agg["defect_terms_next"] >= 2 * agg["defect_roll3_baseline"]
    )

    agg["risk_event"] = (cond_1star | cond_rating_drop | cond_defect).astype(int)

    # Drop rows where next month is NaN (can't compute label)
    agg = agg.dropna(subset=["pct_1star_next"])
    agg["risk_event"] = agg["risk_event"].astype(int)

    return agg
