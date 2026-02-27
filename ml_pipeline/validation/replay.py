"""
Historical Revenue Impact Replay.

1. Find ONE product with sharp rating drop in the dataset (any year).
2. Find drop_month and heal_month → manual_time = months to fix.
3. Copy that product's actual data, shift dates to post-2020.
4. Run model on copied data → when does model flag it?
5. Compare: months_saved = manual_time - months_until_model_alert.
6. Revenue saved = monthly_rev * months_saved * recovery_rate.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def find_product_with_sharp_drop(agg: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Scan all products. Find ONE with:
    - Sharp drop: avg_rating falls >= 0.7 from 3-month baseline.
    - Clear heal: rating recovers to baseline - 0.2 within 6 months.
    Returns: product, drop_month, heal_month, manual_months, series.
    """
    agg = agg.copy()
    agg["month_dt"] = pd.to_datetime(agg["month"] + "-01")
    agg = agg.sort_values(["asin", "month_dt"]).reset_index(drop=True)

    best = None
    best_drop = -1

    for asin, grp in agg.groupby("asin"):
        grp = grp.sort_values("month_dt").reset_index(drop=True)
        rat = grp["avg_rating"].values
        months = grp["month"].tolist()
        if len(rat) < 5:
            continue
        baseline = np.mean(rat[:3])
        for i in range(2, len(rat) - 2):
            if rat[i] < baseline - 0.7:  # sharp drop
                drop_idx = i
                heal_idx = None
                for j in range(i + 1, min(i + 7, len(rat))):
                    if rat[j] >= baseline - 0.2:
                        heal_idx = j
                        break
                if heal_idx is not None:
                    drop_size = float(baseline - rat[i])
                    if drop_size > best_drop:
                        best_drop = drop_size
                        drop_dt = pd.Timestamp(months[drop_idx] + "-01")
                        heal_dt = pd.Timestamp(months[heal_idx] + "-01")
                        manual_months = max(1, (heal_dt - drop_dt).days // 30)
                        if manual_months > 12:  # skip if heal took >1 year
                            continue
                        series = grp.iloc[max(0, drop_idx - 2) : heal_idx + 2][
                            ["month", "month_dt", "review_count", "avg_rating"]
                        ].to_dict("records")
                        best = {
                            "product": asin,
                            "drop_month": months[drop_idx],
                            "heal_month": months[heal_idx],
                            "manual_months": manual_months,
                            "drop_size": drop_size,
                            "series": series,
                        }
    return best


def copy_and_shift_to_post_2020(
    agg: pd.DataFrame,
    product: str,
    drop_month: str,
    n_months: int = 6,
) -> pd.DataFrame:
    """
    Copy product's rows starting at drop_month. Reassign month to 2020-01, 2020-02, ...
    """
    product_rows = agg[(agg["asin"] == product)].sort_values("month_dt").reset_index(drop=True)
    if len(product_rows) == 0:
        return pd.DataFrame()
    mask = product_rows["month"] == drop_month
    start = product_rows[mask].index[0] if mask.any() else 0
    pos = product_rows.index.get_loc(start) if mask.any() else 0
    slice_df = product_rows.iloc[pos : pos + n_months].copy()
    if len(slice_df) == 0:
        return pd.DataFrame()
    new_months = pd.date_range("2020-01-01", periods=len(slice_df), freq="MS")
    slice_df["month"] = [d.strftime("%Y-%m") for d in new_months]
    slice_df["month_dt"] = new_months
    return slice_df


def run_visual_replay(
    raw_df: pd.DataFrame,
    agg: pd.DataFrame,
    model,
    scaler,
    feature_cols: list,
    risk_threshold: float = 0.5,
    recovery_rate: float = 0.4,
) -> dict:
    """
    1. Find product with sharp drop.
    2. Original: visualize drop → heal, manual_months.
    3. Copy data to post-2020, run model.
    4. Model alert vs manual → months_saved, revenue.
    """
    for c in ["ticket_count", "high_severity_rate", "resolution_time_avg"]:
        if c in feature_cols and c not in agg.columns:
            agg[c] = 0.0
    feature_cols = [c for c in feature_cols if c in agg.columns]

    incident = find_product_with_sharp_drop(agg)
    if incident is None:
        return {
            "original": {"product": None, "drop_month": None, "heal_month": None, "manual_months": 0, "series": []},
            "replay_series": [],
            "model_alert": None,
            "manual_month": None,
            "months_saved": 0,
            "revenue_saved": 0,
        }

    product = incident["product"]
    drop_month = incident["drop_month"]
    heal_month = incident["heal_month"]
    manual_months = incident["manual_months"]

    # Copy that product's data and shift to post-2020
    replayed = copy_and_shift_to_post_2020(agg, product, drop_month, n_months=min(6, manual_months + 2))
    if len(replayed) == 0:
        replayed = copy_and_shift_to_post_2020(agg, product, drop_month, n_months=6)

    if len(replayed) == 0:
        return {
            "original": incident,
            "replay_series": [],
            "model_alert": None,
            "manual_month": None,
            "months_saved": 0,
            "revenue_saved": 0,
        }

    X = replayed[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    if scaler is not None:
        X = scaler.transform(X)
    proba = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(X)
    replayed = replayed.copy()
    replayed["risk_probability"] = proba

    replay_series = replayed[["month", "month_dt", "risk_probability", "avg_rating", "review_count"]].copy()
    replay_series = replay_series.rename(columns={"risk_probability": "risk_prob"})
    replay_series = replay_series.to_dict("records")

    # Model alert = first month risk >= threshold
    alert_rows = replayed[replayed["risk_probability"] >= risk_threshold]
    model_alert_month = alert_rows["month"].iloc[0] if len(alert_rows) > 0 else None

    # Manual would have acted at drop_start + manual_months (in replay, drop_start = 2020-01)
    first_month = replayed["month_dt"].min()
    manual_dt = first_month + pd.DateOffset(months=manual_months)
    manual_month = manual_dt.strftime("%Y-%m")

    months_saved = 0
    if model_alert_month:
        model_dt = pd.Timestamp(model_alert_month + "-01")
        months_saved = max(0, (manual_dt - model_dt).days // 30)

    monthly_rev = (2.8e9 / 12) / 40
    revenue_saved = monthly_rev * months_saved * recovery_rate

    return {
        "original": {
            "product": product,
            "drop_month": drop_month,
            "heal_month": heal_month,
            "manual_months": manual_months,
            "series": incident["series"],
        },
        "replay_series": replay_series,
        "model_alert": model_alert_month,
        "manual_month": manual_month,
        "months_saved": int(months_saved),
        "revenue_saved": revenue_saved,
    }
