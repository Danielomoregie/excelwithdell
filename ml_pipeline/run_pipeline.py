"""
Main pipeline: load data, feature engineering, labels, temporal split,
train models, revenue scoring, outputs, and visualizations.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings

from ml_pipeline.database.loader import load_data
from ml_pipeline.features.engineer import build_features
from ml_pipeline.features.labels import compute_labels
from ml_pipeline.models.trainer import train_models, temporal_split, _get_feature_cols, prepare_xy
from ml_pipeline.models.explain import get_logistic_coefficients, get_xgboost_importance, compute_shap_values
from ml_pipeline.utils.config import OUTPUT_DIR, ensure_output_dir, TRAIN_FRAC
from ml_pipeline.utils.revenue import add_revenue_exposure, compute_revenue_summary
from ml_pipeline.simulation.tickets import simulate_synthetic_support_tickets
from ml_pipeline.validation.replay import run_replay_validation

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False


def run_full_pipeline(
    data_source: str = "csv",
    csv_path: Path = None,
    run_simulation: bool = True,
    run_replay: bool = True,
) -> dict:
    """
    Execute full ML pipeline and save outputs.
    Returns dict with models, feature importance, predictions, etc.
    """
    ensure_output_dir()
    outputs = {}

    # 1. Load data
    print("Loading data...")
    df = load_data(source=data_source, csv_path=csv_path)
    print(f"  Loaded {len(df)} reviews")

    # 2. Feature engineering
    print("Building features...")
    support_tickets = None
    if run_simulation:
        # Build initial agg for ticket simulation (no labels yet)
        from ml_pipeline.features.engineer import aggregate_to_asin_month, add_rolling_features, add_pct_verified
        agg_temp = aggregate_to_asin_month(df)
        agg_temp = add_rolling_features(agg_temp)
        agg_temp = add_pct_verified(agg_temp)
        support_tickets = simulate_synthetic_support_tickets(agg_temp, trend_type="none", duration_months=6)

    agg = build_features(df, support_tickets=support_tickets)
    print(f"  Aggregated to {len(agg)} ASIN×Month rows")

    # 3. Labels (risk_event)
    agg = compute_labels(agg)
    print(f"  Labels: {agg['risk_event'].sum()} risk events")

    # 4. Temporal split
    train_df, test_df = temporal_split(agg, train_frac=TRAIN_FRAC)
    feature_cols = _get_feature_cols(agg)
    print(f"  Train: {len(train_df)}, Test: {len(test_df)} | Features: {len(feature_cols)}")

    # 5. Train models
    print("Training models...")
    results, feature_cols, X_test, y_test = train_models(train_df, test_df, OUTPUT_DIR)
    outputs["results"] = results
    outputs["feature_cols"] = feature_cols

    # Use best model (XGB if available, else LogReg) for predictions
    best_model_name = "xgboost" if HAS_XGB and results.get("xgboost") else "logistic_regression"
    best = results[best_model_name]
    model = best["model"]
    scaler = best.get("scaler")

    X_test_df = test_df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    if scaler is not None:
        X_test_scaled = scaler.transform(X_test_df)
        proba = model.predict_proba(X_test_scaled)[:, 1]
    else:
        proba = model.predict_proba(X_test_df)[:, 1]

    # 6. Monthly risk predictions + revenue
    pred_df = test_df[["asin", "month", "month_dt", "risk_event"]].copy()
    pred_df["risk_probability"] = proba
    pred_df = add_revenue_exposure(pred_df)
    pred_df.to_csv(OUTPUT_DIR / "monthly_risk_predictions.csv", index=False)
    outputs["predictions"] = pred_df

    # 7. Feature importance
    lr_imp = get_logistic_coefficients(results["logistic_regression"]["model"], feature_cols)
    lr_imp.to_csv(OUTPUT_DIR / "feature_importance_logistic.csv", index=False)
    if HAS_XGB and results.get("xgboost"):
        xgb_imp = get_xgboost_importance(results["xgboost"]["model"], feature_cols)
        xgb_imp.to_csv(OUTPUT_DIR / "feature_importance_xgboost.csv", index=False)
        # Use xgb importance as primary
        feature_importance = xgb_imp
    else:
        feature_importance = lr_imp.rename(columns={"abs_coefficient": "importance"})[["feature", "importance"]]
    feature_importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)

    # 8. Revenue impact summary
    rev_summary = compute_revenue_summary(pred_df)
    rev_summary.to_csv(OUTPUT_DIR / "revenue_impact_summary.csv", index=False)
    outputs["revenue_summary"] = rev_summary

    # 9. Replay validation
    if run_replay and "risk_event" in test_df.columns:
        replay = run_replay_validation(
            agg, model, scaler, feature_cols, cutoff_year=2016
        )
        outputs["replay"] = replay

    # 10. Save best model as trained_model.pkl
    with open(OUTPUT_DIR / "trained_model.pkl", "wb") as f:
        import pickle
        pickle.dump({
            "model": model,
            "scaler": scaler,
            "feature_cols": feature_cols,
            "model_name": best_model_name,
        }, f)

    # 11. Generate visualizations
    _generate_visualizations(pred_df, feature_importance, results, best_model_name)

    print(f"\nOutputs saved to {OUTPUT_DIR}")
    print("  - trained_model.pkl")
    print("  - feature_importance.csv")
    print("  - monthly_risk_predictions.csv")
    print("  - revenue_impact_summary.csv")
    print("  - risk_trend.png, feature_importance_plot.png, confusion_matrix.png")
    return outputs


def _generate_visualizations(pred_df, feature_importance, results, best_model_name):
    """Generate risk trend and anomaly overlay plots."""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")

    fig1, ax1 = plt.subplots(figsize=(10, 5))
    monthly = pred_df.groupby("month")["risk_probability"].mean().reset_index()
    monthly["month_dt"] = pd.to_datetime(monthly["month"] + "-01")
    monthly = monthly.sort_values("month_dt")
    ax1.plot(monthly["month_dt"], monthly["risk_probability"], marker="o", markersize=4)
    ax1.set_xlabel("Month")
    ax1.set_ylabel("Mean Risk Probability")
    ax1.set_title("Risk Trend Over Time")
    ax1.grid(True, alpha=0.3)
    fig1.tight_layout()
    fig1.savefig(OUTPUT_DIR / "risk_trend.png", dpi=100, bbox_inches="tight")
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.barh(feature_importance["feature"].head(12), feature_importance["importance"].head(12))
    ax2.set_xlabel("Importance")
    ax2.set_title("Top Feature Importance")
    ax2.invert_yaxis()
    fig2.tight_layout()
    fig2.savefig(OUTPUT_DIR / "feature_importance_plot.png", dpi=100, bbox_inches="tight")
    plt.close(fig2)

    best = results[best_model_name]
    cm = best["confusion_matrix"]
    fig3, ax3 = plt.subplots(figsize=(5, 4))
    im = ax3.imshow(cm, cmap="Blues")
    ax3.set_xticks([0, 1])
    ax3.set_yticks([0, 1])
    ax3.set_xticklabels(["No Risk", "Risk"])
    ax3.set_yticklabels(["No Risk", "Risk"])
    ax3.set_xlabel("Predicted")
    ax3.set_ylabel("Actual")
    for i in range(2):
        for j in range(2):
            ax3.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
    ax3.set_title(f"Confusion Matrix ({best_model_name})")
    fig3.tight_layout()
    fig3.savefig(OUTPUT_DIR / "confusion_matrix.png", dpi=100, bbox_inches="tight")
    plt.close(fig3)


if __name__ == "__main__":
    run_full_pipeline(data_source="csv")
