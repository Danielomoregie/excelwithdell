import json
import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from Neon_Accessibility_Helper_Functions import close_connection, get_connection
from Sentiment_Analyzer import analyze_sentiment, clean_review_text
from Theme_Extractor import classify_review_themes

# ==============================
# THRESHOLD CONFIGURATION
# ==============================
# Adjust HIGH_RISK_THRESHOLD to control precision/recall trade-off
# Lower threshold (e.g., 25, 50) → Higher recall, lower precision (catch more risk)
# Higher threshold (e.g., 75, 90) → Lower recall, higher precision (only certain risks)
# Each training run tracks which threshold was used, allowing easy comparison across runs
# NOTE: This is the INITIAL threshold. After evaluation, the OPTIMAL threshold is computed
# using F1 score and automatically selected during model evaluation.
# NOTE: The initial threshold below is used as a baseline. However, during evaluation,
# the system automatically computes the OPTIMAL threshold using F1 score maximization.
# This ensures we find the best precision/recall balance for your data.
#
# If you want to force a specific threshold (not recommended), change the value below.
HIGH_RISK_THRESHOLD = 50  # Initial threshold; OPTIMAL is auto-computed via F1 score

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
EVALUATION_DATASET_PATH = os.path.join(MODELS_DIR, "evaluation_reviews.csv")
VALIDATION_REPORT_PATH = os.path.join(MODELS_DIR, "Validation_Report.json")
MODEL_REGISTRY_PATH = os.path.join(MODELS_DIR, "model_registry.json")
BASELINE_METRICS_PATH = os.path.join(MODELS_DIR, "baseline_metrics.json")
CURRENT_PRODUCTION_MODEL_PATH = os.path.join(MODELS_DIR, "current_production_model.pkl")
LEGACY_ARTIFACT_ALIAS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")
TESTING_TABLE = "cleaned_test_20_percent"
TESTING_CSV_FALLBACK = os.path.join(
    os.path.dirname(__file__),
    "..",
    "Dataset_Scripts",
    "Training_Testing_Split",
    "cleaned_test_20_percent.csv",
)


def _ensure_models_dir():
    os.makedirs(MODELS_DIR, exist_ok=True)


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, payload):
    _ensure_models_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _risk_level_from_score(score):
    if score is None:
        return "LOW"
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _sanitize_risk_level(value):
    raw = str(value or "").strip().upper()
    if raw in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return raw
    return "LOW"


def _safe_float(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def load_testing_reviews():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql(
            f"SELECT * FROM {TESTING_TABLE} ORDER BY date ASC",
            conn,
        )
        return df
    except Exception:
        if os.path.exists(TESTING_CSV_FALLBACK):
            return pd.read_csv(TESTING_CSV_FALLBACK)
        raise
    finally:
        if conn is not None:
            try:
                close_connection(conn)
            except Exception:
                pass


def _seed_labels_from_review(row):
    rating = _safe_float(row.get("rating"), 3.0)
    text = str(row.get("text", "") or "")
    title = str(row.get("title_x", "") or "")

    review_df = pd.DataFrame(
        [{"text": text, "title_x": title, "rating": rating, "asin": row.get("asin", "")}]
    )
    analyzed = analyze_sentiment(review_df)
    sentiment = str(analyzed.iloc[0].get("sentiment_label", "neutral")).lower()
    themes = classify_review_themes(clean_review_text(text))
    top_theme = themes[0] if themes else "general"

    base = 20.0
    if sentiment == "negative":
        base += 40.0
    elif sentiment == "neutral":
        base += 15.0

    if rating is not None:
        base += max(0.0, (5.0 - rating) * 10.0)

    base += min(len(themes), 3) * 7.5
    severity = max(0.0, min(100.0, round(base, 1)))
    risk_level = _risk_level_from_score(severity)

    return {
        "labeled_issue": top_theme,
        "labeled_severity_score": severity,
        "labeled_risk_level": risk_level,
    }


def ensure_evaluation_dataset(test_df, sample_size=300):
    _ensure_models_dir()

    if os.path.exists(EVALUATION_DATASET_PATH):
        df = pd.read_csv(EVALUATION_DATASET_PATH)
        # Keep backward compatibility if the file already exists.
        expected_cols = [
            "review_id",
            "asin",
            "product_name",
            "review_text",
            "rating",
            "labeled_issue",
            "labeled_severity_score",
            "labeled_risk_level",
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = "" if col != "labeled_severity_score" else np.nan
        return df[expected_cols]

    # Seed from 20% testing dataset; human reviewers can update labels later.
    if "date" in test_df.columns:
        test_df = test_df.sort_values("date")

    sampled = test_df.head(sample_size).copy()
    rows = []
    for i, (_, r) in enumerate(sampled.iterrows(), start=1):
        seeded = _seed_labels_from_review(r)
        rows.append(
            {
                "review_id": str(r.get("review_id", i)),
                "asin": str(r.get("asin", "")),
                "product_name": str(r.get("title_y", "Unknown Product")),
                "review_text": str(r.get("text", "")),
                "rating": _safe_float(r.get("rating"), None),
                "labeled_issue": seeded["labeled_issue"],
                "labeled_severity_score": seeded["labeled_severity_score"],
                "labeled_risk_level": seeded["labeled_risk_level"],
            }
        )

    evaluation_df = pd.DataFrame(rows)
    evaluation_df.to_csv(EVALUATION_DATASET_PATH, index=False)
    return evaluation_df


def predict_product(asin, artifacts):
    risk = artifacts.get("risk_results", {}) if isinstance(artifacts, dict) else {}
    return risk.get(str(asin), {})


def predict_review(review_row, artifacts):
    asin = str(review_row.get("asin", ""))
    text = str(review_row.get("review_text", "") or "")
    title = str(review_row.get("product_name", "") or "")[:120]
    rating = _safe_float(review_row.get("rating"), 3.0)

    review_df = pd.DataFrame([{"text": text, "title_x": title, "rating": rating, "asin": asin}])
    analyzed = analyze_sentiment(review_df)
    sentiment_score = float(analyzed.iloc[0].get("combined_sentiment", 0.0))
    sentiment_label = str(analyzed.iloc[0].get("sentiment_label", "neutral")).lower()

    themes = classify_review_themes(clean_review_text(text))
    product_pred = predict_product(asin, artifacts)
    product_risk_score = product_pred.get("risk_score")
    if product_risk_score is None:
        product_risk_score = 35.0

    sentiment_severity = (1.0 - sentiment_score) * 50.0  # map [-1,1] -> [100,0]
    rating_severity = max(0.0, min(100.0, (5.0 - rating) * 25.0))
    theme_severity = min(len(themes), 4) * 12.5

    predicted_severity = (
        0.35 * sentiment_severity
        + 0.20 * rating_severity
        + 0.15 * theme_severity
        + 0.30 * float(product_risk_score)
    )
    predicted_severity = round(max(0.0, min(100.0, predicted_severity)), 2)

    return {
        "predicted_severity_score": predicted_severity,
        "predicted_risk_level": _risk_level_from_score(predicted_severity),
        "predicted_sentiment_label": sentiment_label,
        "predicted_issue": themes[0] if themes else "general",
        "predicted_product_risk_score": float(product_risk_score),
    }


def _time_to_detection_advantage(eval_scored_df):
    if "date" not in eval_scored_df.columns:
        return 0

    advantages = []
    df = eval_scored_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return 0

    for asin, group in df.groupby("asin"):
        group = group.sort_values("date")
        if len(group) < 3:
            continue

        model_high = group[group["predicted_severity_score"] >= HIGH_RISK_THRESHOLD]
        threshold_high = group[group["rating"].astype(float) <= 2]

        if model_high.empty:
            continue
        model_first = model_high.iloc[0]["date"]

        if threshold_high.empty:
            advantages.append(2)
            continue

        threshold_first = threshold_high.iloc[0]["date"]
        diff_months = (threshold_first - model_first).days / 30.0
        advantages.append(round(diff_months, 2))

    if not advantages:
        return 0
    return round(float(np.mean(advantages)), 2)


def _compute_optimal_threshold(labeled, predicted):
    """
    Find the optimal threshold that maximizes F1 score.
    
    Returns dict with optimal threshold metrics and ROC AUC.
    """
    try:
        from sklearn.metrics import precision_recall_curve, roc_auc_score
    except ImportError:
        # Fallback if sklearn not available
        return {
            "optimal_threshold": HIGH_RISK_THRESHOLD,
            "optimal_f1_score": None,
            "optimal_recall": None,
            "optimal_precision": None,
            "roc_auc_score": None,
        }
    
    try:
        # Binary classification: is labeled_score >= 50 (high-risk)?
        y_true = (labeled >= 50).astype(int)
        
        # Compute precision-recall curve
        precision_arr, recall_arr, thresholds = precision_recall_curve(y_true, predicted)
        
        # Compute F1 for each threshold
        f1_scores = 2 * (precision_arr * recall_arr) / (precision_arr + recall_arr + 1e-8)
        best_idx = np.argmax(f1_scores)
        
        optimal_threshold = float(thresholds[best_idx]) if best_idx < len(thresholds) else 50.0
        optimal_f1 = float(f1_scores[best_idx])
        optimal_precision = float(precision_arr[best_idx])
        optimal_recall = float(recall_arr[best_idx])
        
        # Compute ROC AUC
        try:
            roc_auc = float(roc_auc_score(y_true, predicted))
        except Exception:
            roc_auc = None
        
        return {
            "optimal_threshold": round(optimal_threshold, 2),
            "optimal_f1_score": round(optimal_f1, 4),
            "optimal_recall": round(optimal_recall, 4),
            "optimal_precision": round(optimal_precision, 4),
            "roc_auc_score": round(roc_auc, 4) if roc_auc else None,
        }
    except Exception as e:
        print(f"Warning: Could not compute optimal threshold: {e}")
        return {
            "optimal_threshold": HIGH_RISK_THRESHOLD,
            "optimal_f1_score": None,
            "optimal_recall": None,
            "optimal_precision": None,
            "roc_auc_score": None,
        }


def run_model_evaluation(artifacts, candidate_version, evaluation_df):
    scored_rows = []

    for _, row in evaluation_df.iterrows():
        pred = predict_review(row, artifacts)
        labeled_score = _safe_float(row.get("labeled_severity_score"), None)
        if labeled_score is None:
            continue

        labeled_risk_level = _sanitize_risk_level(row.get("labeled_risk_level"))
        scored_rows.append(
            {
                "review_id": str(row.get("review_id", "")),
                "asin": str(row.get("asin", "")),
                "product_name": str(row.get("product_name", "")),
                "review_text": str(row.get("review_text", "")),
                "rating": _safe_float(row.get("rating"), 0.0),
                "labeled_issue": str(row.get("labeled_issue", "")).strip().lower(),
                "labeled_severity_score": float(labeled_score),
                "labeled_risk_level": labeled_risk_level,
                **pred,
            }
        )

    if not scored_rows:
        report = {
            "model_version": candidate_version,
            "error": "No labeled evaluation rows with valid labeled_severity_score",
            "evaluated_reviews": 0,
        }
        _save_json(VALIDATION_REPORT_PATH, report)
        return report

    df = pd.DataFrame(scored_rows)
    labeled = df["labeled_severity_score"].astype(float).to_numpy()
    predicted = df["predicted_severity_score"].astype(float).to_numpy()

    pearson = float(np.corrcoef(predicted, labeled)[0, 1]) if len(df) > 1 else 0.0
    if np.isnan(pearson):
        pearson = 0.0

    mae = float(np.mean(np.abs(predicted - labeled)))

    labeled_high = labeled >= HIGH_RISK_THRESHOLD
    predicted_high = predicted >= HIGH_RISK_THRESHOLD

    directional_accuracy = float(np.mean(labeled_high == predicted_high)) if len(df) else 0.0

    tp = int(np.sum(predicted_high & labeled_high))
    fp = int(np.sum(predicted_high & ~labeled_high))
    fn = int(np.sum(~predicted_high & labeled_high))

    high_risk_recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 1.0
    high_risk_precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 1.0

    score_drift = float(np.mean(predicted - labeled))
    time_advantage = _time_to_detection_advantage(df)

    level_match = (
        df["labeled_risk_level"].astype(str).str.upper()
        == df["predicted_risk_level"].astype(str).str.upper()
    )
    risk_level_accuracy = float(level_match.mean()) if len(df) else 0.0
    
    # Compute optimal threshold using F1 score
    optimal_metrics = _compute_optimal_threshold(labeled, predicted)

    report = {
        "model_version": candidate_version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "evaluated_reviews": int(len(df)),
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
        "pearson_correlation": round(pearson, 4),
        "mae": round(mae, 4),
        "high_risk_recall": round(high_risk_recall, 4),
        "high_risk_precision": round(high_risk_precision, 4),
        "directional_accuracy": round(directional_accuracy, 4),
        "risk_level_accuracy": round(risk_level_accuracy, 4),
        "score_drift": round(score_drift, 4),
        "time_to_detection_advantage_months": time_advantage,
        "roc_auc": optimal_metrics.get("roc_auc_score"),
        "optimal_threshold_metrics": optimal_metrics,
        "distribution": {
            "predicted_scores": [round(float(v), 3) for v in predicted[:300].tolist()],
            "labeled_scores": [round(float(v), 3) for v in labeled[:300].tolist()],
        },
        "review_samples": df.head(60).to_dict(orient="records"),
    }

    _save_json(VALIDATION_REPORT_PATH, report)
    return report


def _performance_score(metrics):
    """
    Composite score for model evaluation combining multiple dimensions.
    Weighs F1 score heavily since it balances precision and recall.
    """
    pearson_component = (float(metrics.get("pearson_correlation", 0.0)) + 1.0) / 2.0
    directional = float(metrics.get("directional_accuracy", 0.0))
    
    # Use optimal F1 score if available, otherwise compute from recall/precision
    optimal_f1 = metrics.get("optimal_f1_score")
    if optimal_f1 is not None:
        recall_precision = optimal_f1
    else:
        recall = float(metrics.get("high_risk_recall", 0.0))
        precision = float(metrics.get("high_risk_precision", 0.0))
        recall_precision = 2 * (precision * recall) / (precision + recall + 1e-8) if (precision + recall) > 0 else 0.0
    
    mae = float(metrics.get("mae", 100.0))
    mae_component = max(0, 1.0 - (mae / 50.0))  # Penalize MAE > 50
    
    roc_auc = metrics.get("roc_auc")
    roc_component = float(roc_auc) if roc_auc is not None else 0.5

    return (
        0.25 * pearson_component
        + 0.25 * recall_precision
        + 0.20 * directional
        + 0.15 * mae_component
        + 0.15 * roc_component
    )


def _extract_metric_snapshot(report):
    return {
        "pearson_correlation": float(report.get("pearson_correlation", 0.0)),
        "mae": float(report.get("mae", 100.0)),
        "high_risk_recall": float(report.get("high_risk_recall", 0.0)),
        "high_risk_precision": float(report.get("high_risk_precision", 0.0)),
        "directional_accuracy": float(report.get("directional_accuracy", 0.0)),
        "risk_level_accuracy": float(report.get("risk_level_accuracy", 0.0)),
        "score_drift": float(report.get("score_drift", 0.0)),
        "time_to_detection_advantage_months": float(report.get("time_to_detection_advantage_months", 0.0)),
        "roc_auc": float(report.get("roc_auc", 0.0)) if report.get("roc_auc") is not None else None,
        "optimal_threshold": float((report.get("optimal_threshold_metrics", {}) or {}).get("optimal_threshold", 0.0)) if (report.get("optimal_threshold_metrics", {}) or {}).get("optimal_threshold") is not None else None,
        "optimal_f1_score": float((report.get("optimal_threshold_metrics", {}) or {}).get("optimal_f1_score", 0.0)) if (report.get("optimal_threshold_metrics", {}) or {}).get("optimal_f1_score") is not None else None,
        "optimal_recall": float((report.get("optimal_threshold_metrics", {}) or {}).get("optimal_recall", 0.0)) if (report.get("optimal_threshold_metrics", {}) or {}).get("optimal_recall") is not None else None,
        "optimal_precision": float((report.get("optimal_threshold_metrics", {}) or {}).get("optimal_precision", 0.0)) if (report.get("optimal_threshold_metrics", {}) or {}).get("optimal_precision") is not None else None,
    }


def register_and_maybe_deploy(candidate_artifacts, evaluation_report):
    _ensure_models_dir()

    registry = _load_json(MODEL_REGISTRY_PATH, default=[])
    if not isinstance(registry, list):
        registry = []

    baseline_metrics = _load_json(BASELINE_METRICS_PATH, default={})
    training_run_number = len(registry)

    deployed_entries = [r for r in registry if r.get("deployed")]
    latest_deployed = deployed_entries[-1] if deployed_entries else None

    if latest_deployed:
        current_deployed_version = int(latest_deployed.get("deployed_model_version", 0))
        current_metrics = latest_deployed.get("metrics", {})
    else:
        current_deployed_version = -1
        current_metrics = {}

    optimal_threshold_metrics = evaluation_report.get("optimal_threshold_metrics", {}) or {}
    operating_threshold = optimal_threshold_metrics.get("optimal_threshold")
    if operating_threshold is None:
        operating_threshold = evaluation_report.get("high_risk_threshold", HIGH_RISK_THRESHOLD)

    # Persist operating threshold into artifact metadata so deployed inference is consistent.
    if isinstance(candidate_artifacts, dict):
        metadata = candidate_artifacts.get("model_metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            candidate_artifacts["model_metadata"] = metadata
        metadata["operating_high_risk_threshold"] = float(operating_threshold)

    candidate_metrics = _extract_metric_snapshot(evaluation_report)
    candidate_score = _performance_score(candidate_metrics)
    current_score = _performance_score(current_metrics) if current_metrics else -1

    # Deploy if: no current model, OR candidate is reasonably competitive (>-0.05% relative to current)
    # Stricter gate: only allows 0.05% relative decline to ensure quality improvements
    should_deploy = (latest_deployed is None) or (candidate_score >= current_score * 0.9995)

    deployed_model_version = current_deployed_version
    deployed_model_path = None

    if should_deploy:
        deployed_model_version = current_deployed_version + 1
        deployed_model_path = os.path.join(MODELS_DIR, f"model_{deployed_model_version}.pkl")

        with open(deployed_model_path, "wb") as f:
            pickle.dump(candidate_artifacts, f)

        with open(CURRENT_PRODUCTION_MODEL_PATH, "wb") as f:
            pickle.dump(candidate_artifacts, f)

        # Maintain legacy filename so existing tools keep working.
        with open(LEGACY_ARTIFACT_ALIAS_PATH, "wb") as f:
            pickle.dump(candidate_artifacts, f)

        if not baseline_metrics:
            baseline_metrics = {
                "baseline_model_version": deployed_model_version,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metrics": candidate_metrics,
            }
            _save_json(BASELINE_METRICS_PATH, baseline_metrics)

    run_record = {
        "run_id": f"run_{training_run_number}",
        "run_number": training_run_number,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "candidate_model_version": current_deployed_version + 1,
        "deployed_model_version": deployed_model_version if should_deploy else current_deployed_version,
        "deployed": bool(should_deploy),
        "artifact_path": deployed_model_path,
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
        "operating_high_risk_threshold": operating_threshold,
        "optimal_threshold_metrics": evaluation_report.get("optimal_threshold_metrics", {}),
        "metrics": candidate_metrics,
        "composite_score": round(candidate_score, 6),
        "compared_against_score": round(current_score, 6) if current_score >= 0 else None,
    }

    registry.append(run_record)
    _save_json(MODEL_REGISTRY_PATH, registry)

    return {
        "registry": registry,
        "latest_run": run_record,
        "baseline_metrics": baseline_metrics,
        "deployed": should_deploy,
        "current_production_model_path": CURRENT_PRODUCTION_MODEL_PATH,
        "current_production_version": run_record["deployed_model_version"],
    }
