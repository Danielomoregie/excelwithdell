"""
Model explainability: feature coefficients (LogReg) and SHAP (XGBoost).
"""
import pandas as pd
import numpy as np
from pathlib import Path

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


def get_logistic_coefficients(model, feature_cols: list) -> pd.DataFrame:
    """Feature importance from Logistic Regression coefficients."""
    coef = model.coef_[0]
    importance = pd.DataFrame({
        "feature": feature_cols,
        "coefficient": coef,
        "abs_coefficient": np.abs(coef),
    }).sort_values("abs_coefficient", ascending=False)
    return importance


def get_xgboost_importance(model, feature_cols: list) -> pd.DataFrame:
    """Feature importance from XGBoost."""
    imp = model.feature_importances_
    return pd.DataFrame({
        "feature": feature_cols,
        "importance": imp,
    }).sort_values("importance", ascending=False)


def compute_shap_values(model, X: pd.DataFrame) -> tuple:
    """Compute SHAP values for XGBoost."""
    if not HAS_SHAP:
        return None, None
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        return explainer, shap_values
    except Exception:
        return None, None
