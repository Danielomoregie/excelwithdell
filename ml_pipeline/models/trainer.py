"""
Model training: Logistic Regression (interpretable) and XGBoost (performance).
Evaluation: Precision, Recall, F1, PR-AUC, Confusion Matrix.
"""
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, confusion_matrix,
    classification_report
)
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

FEATURE_COLS = [
    "review_count", "avg_helpful_votes", "pct_verified",
    "avg_rating", "pct_1star", "pct_2star", "rating_trend",
    "defect_terms_rate", "return_terms_rate", "safety_terms_rate", "negative_sentiment_score",
    "avg_rating_roll1", "avg_rating_roll3", "defect_terms_roll1", "defect_terms_roll3",
    "defect_1m_lag", "rating_1m_lag", "rolling_volatility",
    "ticket_count", "high_severity_rate", "resolution_time_avg",  # if support tickets exist
]


def _get_feature_cols(agg: pd.DataFrame) -> list:
    """Return available feature columns (some may be missing)."""
    return [c for c in FEATURE_COLS if c in agg.columns]


def temporal_split(agg: pd.DataFrame, train_frac: float = 0.8):
    """
    Chronological 80/20 split. No random shuffle, no look-ahead.
    """
    agg = agg.sort_values("month_dt").reset_index(drop=True)
    n = len(agg)
    split_idx = int(n * train_frac)
    train_df = agg.iloc[:split_idx]
    test_df = agg.iloc[split_idx:]
    return train_df, test_df


def prepare_xy(df: pd.DataFrame, feature_cols: list):
    """Prepare X, y for training."""
    X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    y = df["risk_event"]
    return X, y


def train_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    random_state: int = 42,
) -> dict:
    """
    Train Logistic Regression and XGBoost. Return metrics and save models.
    """
    feature_cols = _get_feature_cols(train_df)
    if len(feature_cols) < 3:
        raise ValueError(f"Need at least 3 features, got: {feature_cols}")

    X_train, y_train = prepare_xy(train_df, feature_cols)
    X_test, y_test = prepare_xy(test_df, feature_cols)

    # Standardize for LogReg
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = {}

    # --- Logistic Regression ---
    lr = LogisticRegression(max_iter=1000, random_state=random_state, class_weight="balanced")
    lr.fit(X_train_scaled, y_train)
    y_pred_lr = lr.predict(X_test_scaled)
    y_prob_lr = lr.predict_proba(X_test_scaled)[:, 1]

    results["logistic_regression"] = {
        "model": lr,
        "scaler": scaler,
        "precision": precision_score(y_test, y_pred_lr, zero_division=0),
        "recall": recall_score(y_test, y_pred_lr, zero_division=0),
        "f1": f1_score(y_test, y_pred_lr, zero_division=0),
        "pr_auc": average_precision_score(y_test, y_prob_lr),
        "confusion_matrix": confusion_matrix(y_test, y_pred_lr),
        "y_pred": y_pred_lr,
        "y_prob": y_prob_lr,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "logistic_regression.pkl", "wb") as f:
        pickle.dump({"model": lr, "scaler": scaler, "feature_cols": feature_cols}, f)

    # --- XGBoost ---
    if HAS_XGB:
        xgb_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=random_state,
        eval_metric="logloss",
        )
        xgb_model.fit(X_train, y_train)  # XGB handles scaling
        y_pred_xgb = xgb_model.predict(X_test)
        y_prob_xgb = xgb_model.predict_proba(X_test)[:, 1]

        results["xgboost"] = {
            "model": xgb_model,
            "scaler": None,
            "precision": precision_score(y_test, y_pred_xgb, zero_division=0),
            "recall": recall_score(y_test, y_pred_xgb, zero_division=0),
            "f1": f1_score(y_test, y_pred_xgb, zero_division=0),
            "pr_auc": average_precision_score(y_test, y_prob_xgb),
            "confusion_matrix": confusion_matrix(y_test, y_pred_xgb),
            "y_pred": y_pred_xgb,
            "y_prob": y_prob_xgb,
        }
        with open(output_dir / "xgboost_model.pkl", "wb") as f:
            pickle.dump({"model": xgb_model, "feature_cols": feature_cols}, f)
    else:
        results["xgboost"] = None

    return results, feature_cols, X_test, y_test
