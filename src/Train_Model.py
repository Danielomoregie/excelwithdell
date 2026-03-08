import os
import sys
import pickle
import pandas as pd
import json

from Neon_Accessibility_Helper_Functions import get_connection, close_connection
from Sentiment_Analyzer import analyze_sentiment
from Theme_Extractor import train_tfidf_model, extract_themes, get_global_theme_counts
from Risk_Score_Engine import (
    compute_product_risk_scores,
    compute_risk_trends,
    generate_alerts,
    ALERT_THRESHOLDS,
)
from Revenue_Impact_Calculator import (
    calculate_revenue_impact,
    calculate_portfolio_impact,
    TOTAL_ANNUAL_REVENUE,
    MONTHLY_REVENUE,
    NUM_PRODUCTS,
    AVG_PRODUCT_MONTHLY_REVENUE,
    MAX_RISK_IMPACT_PERCENT,
    DEFAULT_RECOVERY_RATE,
)
from Model_Evaluation_And_Versioning import (
    ensure_evaluation_dataset,
    load_testing_reviews,
    register_and_maybe_deploy,
    run_model_evaluation,
    HIGH_RISK_THRESHOLD,
)

# ==============================
# CONFIGURATION
# ==============================

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")
VALIDATION_REPORT_PATH = os.path.join(MODELS_DIR, "Validation_Report.json")
MODEL_REGISTRY_PATH = os.path.join(MODELS_DIR, "model_registry.json")
BASELINE_METRICS_PATH = os.path.join(MODELS_DIR, "baseline_metrics.json")
TRAINING_TABLE = "cleaned_train_80_percent"

UI_DEFAULTS = {
    "dashboard_table_limit": 10,
    "dashboard_alert_limit": 10,
    "dashboard_alert_preview_limit": 5,
    "enabled_departments": ["Engineering & IT", "Marketing", "Sales"],
}

DEV_INFRA_CONFIG = {
    "assumptions": {
        "employees": 15000,
        "avg_reviews_per_employee_per_year": 20,
        "default_avg_review_size_bytes": 2048,
        "model_inference_time_ms": 200,
        "avg_daily_dashboard_queries": 20000,
        "dataset_growth_rate": 0.15,
        "retention_years": 5,
        "active_chat_user_ratio": 0.30,
        "chat_sessions_per_active_user_per_day": 1.2,
        "avg_turns_per_session": 3.5,
        "avg_chat_prompt_tokens": 900,
        "avg_chat_completion_tokens": 300,
        "avg_chars_per_token": 4,
        "chat_inference_time_ms": 900,
        "llm_cost_per_million_tokens": {
            "economy": 0.80,
            "balanced": 2.50,
            "premium": 8.00,
        },
        "training_runs_per_year": 52,
        "cpu_hours_per_run": 3.0,
        "gpu_hours_per_run": 0.8,
        "cpu_cost_per_hour": 1.40,
        "gpu_cost_per_hour": 4.50,
        "mlops_overhead_pct": 0.35,
        "feature_engineering_overhead_ratio": 0.35,
        "vector_index_ratio": 0.25,
        "model_artifacts_bytes": 8 * 1024**3,
        "observability_and_monitoring_bytes": 25 * 1024**3,
    },
    "weights": {
        "compute_weight": 0.30,
        "storage_weight": 0.25,
        "throughput_weight": 0.20,
        "scalability_weight": 0.15,
        "efficiency_weight": 0.10,
    },
    "infrastructures": [
        {
            "name": "PowerEdge",
            "primary_type": "Compute / Servers",
            "compute_capacity": {
                "max_cpus": 2,
                "max_cores_per_cpu": 144,
                "max_ram_tb": 8,
                "max_gpu": 8,
                "compute_index": 1000,
            },
            "storage_capacity": {
                "internal_nvme_tb": 245,
                "cluster_capacity_bytes": 245 * 1024**4,
            },
            "throughput": {
                "note": "Optimized for compute-heavy workloads",
                "throughput_bytes_per_second": 12 * 1024**3,
            },
            "scalability": {
                "max_nodes": 1000,
                "scalability_index": 98,
            },
            "best_for": [
                "AI/ML inference",
                "virtualization",
                "containerized applications",
                "compute-heavy workloads",
            ],
            "efficiency_hint": 88,
        },
        {
            "name": "PowerStore",
            "primary_type": "Block Storage Array",
            "compute_capacity": {
                "compute_index": 230,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "cluster_capacity_pb": 8,
                "cluster_capacity_bytes": 8 * 1024**5,
                "typical_data_reduction": "4:1",
            },
            "throughput": {
                "max_iops": 4_000_000,
                "latency": "sub-ms",
                "throughput_bytes_per_second": 8 * 1024**3,
            },
            "scalability": {
                "max_nodes": 64,
                "scalability_index": 82,
            },
            "best_for": [
                "databases",
                "virtual machines",
                "transactional systems",
            ],
            "efficiency_hint": 76,
        },
        {
            "name": "PowerScale",
            "primary_type": "Scale-Out NAS",
            "compute_capacity": {
                "compute_index": 340,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "max_nodes": 252,
                "cluster_capacity_pb": 186,
                "cluster_capacity_bytes": 186 * 1024**5,
            },
            "throughput": {
                "max_throughput_gbps": 945,
                "max_iops": 15_800_000,
                "throughput_bytes_per_second": 945 * 1024**3,
            },
            "scalability": {
                "max_nodes": 252,
                "scalability_index": 95,
            },
            "best_for": [
                "AI datasets",
                "unstructured data",
                "analytics pipelines",
                "large file repositories",
            ],
            "efficiency_hint": 92,
        },
        {
            "name": "PowerProtect",
            "primary_type": "Backup / Cyber Recovery",
            "compute_capacity": {
                "compute_index": 160,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "logical_capacity_pb": 50,
                "cluster_capacity_bytes": 50 * 1024**5,
                "dedupe": "up to 65:1",
            },
            "throughput": {
                "backup_tb_per_hour": 94,
                "throughput_bytes_per_second": (94 * 1024**4) / 3600,
            },
            "scalability": {
                "max_nodes": 80,
                "scalability_index": 74,
            },
            "best_for": [
                "backup",
                "ransomware protection",
                "archival storage",
            ],
            "efficiency_hint": 55,
        },
    ],
}


# ==============================
# MAIN TRAINING PIPELINE
# ==============================

def main():
    print("=" * 60)
    print("  FusionTech Product Risk Model - Training Pipeline")
    print("=" * 60)

    # ---- Step 1: Pull training data from Neon ----
    print("\n[1/6] Connecting to Neon and pulling training data...")
    conn = get_connection()
    train_df = pd.read_sql(
        f"SELECT * FROM {TRAINING_TABLE} ORDER BY date ASC",
        conn
    )
    close_connection(conn)
    print(f"       Loaded {len(train_df)} reviews from '{TRAINING_TABLE}'")

    # Ensure date column is datetime
    if 'date' in train_df.columns:
        train_df['date'] = pd.to_datetime(train_df['date'], errors='coerce')

    # ---- Step 2: Run sentiment analysis ----
    print("\n[2/6] Running VADER sentiment analysis...")
    enriched_df = analyze_sentiment(train_df)

    pos = (enriched_df['sentiment_label'] == 'positive').sum()
    neg = (enriched_df['sentiment_label'] == 'negative').sum()
    neu = (enriched_df['sentiment_label'] == 'neutral').sum()
    print(f"       Positive: {pos} | Negative: {neg} | Neutral: {neu}")

    # ---- Step 3: Train TF-IDF model ----
    print("\n[3/6] Training TF-IDF vectorizer on negative reviews...")
    tfidf_vectorizer, feature_names = train_tfidf_model(enriched_df)
    if tfidf_vectorizer:
        print(f"       Vocabulary size: {len(feature_names)} terms")
    else:
        print("       Not enough negative reviews to train TF-IDF.")

    # ---- Step 4: Extract themes + compute risk scores ----
    print("\n[4/6] Computing product risk scores...")
    risk_results = compute_product_risk_scores(enriched_df)

    scored = sum(1 for r in risk_results.values() if r['risk_score'] is not None)
    insufficient = sum(1 for r in risk_results.values() if r['risk_score'] is None)
    print(f"       Products scored: {scored} | Insufficient data: {insufficient}")

    # Print top 5 riskiest
    scored_products = [r for r in risk_results.values() if r['risk_score'] is not None]
    scored_products.sort(key=lambda x: x['risk_score'], reverse=True)
    print("\n       Top 5 Riskiest Products:")
    for i, p in enumerate(scored_products[:5]):
        themes = ", ".join(t[0] for t in p['top_themes'][:3]) or "none detected"
        print(f"       {i+1}. [{p['alert_level']}] Score: {p['risk_score']} | "
              f"{p['product_name'][:50]} | Themes: {themes}")

    # ---- Step 5: Add revenue impact to each product ----
    print("\n[5/6] Calculating revenue impact estimates...")
    for asin, data in risk_results.items():
        data['revenue_impact'] = calculate_revenue_impact(data['risk_score'])

    portfolio = calculate_portfolio_impact(risk_results)
    print(f"       Total monthly revenue at risk: ${portfolio['total_monthly_revenue_at_risk']:,.0f}")
    print(f"       Potential monthly savings: ${portfolio['total_potential_monthly_savings']:,.0f}")

    # ---- Step 6: Compute trends + save everything ----
    print("\n[6/6] Computing trends and saving artifacts...")
    risk_trends = compute_risk_trends(enriched_df)
    global_themes = get_global_theme_counts(enriched_df)
    alerts = generate_alerts(risk_results)

    # Build artifacts bundle
    artifacts = {
        "enriched_df": enriched_df,
        "tfidf_vectorizer": tfidf_vectorizer,
        "risk_results": risk_results,
        "risk_trends": risk_trends,
        "global_themes": global_themes,
        "alerts": alerts,
        "portfolio_impact": portfolio,
        "model_metadata": {
            "model_name": "hybrid-risk-v2",
            "model_type": "rule_based_with_bayesian_smoothing",
            "training_table": TRAINING_TABLE,
            "min_reviews": 3,
            "risk_thresholds": ALERT_THRESHOLDS,
            "subscore_weights": {
                "negative_sentiment_ratio": 0.25,
                "sentiment_velocity": 0.15,
                "rating_decline": 0.20,
                "low_rating_spike": 0.15,
                "complaint_concentration": 0.10,
                "community_validated": 0.15,
            },
            "ui_defaults": UI_DEFAULTS,
            "chatbot_response_thresholds": ALERT_THRESHOLDS,
            "financial_assumptions": {
                "total_annual_revenue": TOTAL_ANNUAL_REVENUE,
                "company_monthly_revenue": MONTHLY_REVENUE,
                "num_products": NUM_PRODUCTS,
                "avg_product_monthly_revenue": AVG_PRODUCT_MONTHLY_REVENUE,
                "max_risk_impact_percent": MAX_RISK_IMPACT_PERCENT,
                "default_recovery_rate": DEFAULT_RECOVERY_RATE,
            },
            "dev_infrastructure": DEV_INFRA_CONFIG,
            "notes": "Adds Bayesian smoothing, confidence calibration, and recency boost while preserving output schema.",
        },
    }

    print("\n[7/8] Running manual-labeled evaluation on the 20% testing dataset...")
    testing_df = load_testing_reviews()
    if "date" in testing_df.columns:
        testing_df["date"] = pd.to_datetime(testing_df["date"], errors="coerce")
    evaluation_df = ensure_evaluation_dataset(testing_df)

    existing_registry = []
    if os.path.exists(MODEL_REGISTRY_PATH):
        try:
            with open(MODEL_REGISTRY_PATH, "r", encoding="utf-8") as f:
                existing_registry = json.load(f)
            if not isinstance(existing_registry, list):
                existing_registry = []
        except Exception:
            existing_registry = []

    deployed_runs = [r for r in existing_registry if r.get("deployed")]
    latest_deployed_version = (
        int(deployed_runs[-1].get("deployed_model_version", 0))
        if deployed_runs else -1
    )
    candidate_version = latest_deployed_version + 1

    evaluation_report = run_model_evaluation(
        artifacts=artifacts,
        candidate_version=candidate_version,
        evaluation_df=evaluation_df,
    )

    print("       Validation metrics:")
    print(f"       High-Risk Threshold (initial): {HIGH_RISK_THRESHOLD}")
    print(f"       Pearson: {evaluation_report.get('pearson_correlation', 0)}")
    print(f"       MAE: {evaluation_report.get('mae', 0)}")
    print(f"       Directional Accuracy: {evaluation_report.get('directional_accuracy', 0)}")
    print(f"       High-Risk Recall: {evaluation_report.get('high_risk_recall', 0)}")
    print(f"       High-Risk Precision: {evaluation_report.get('high_risk_precision', 0)}")
    
    # Show optimal threshold metrics
    optimal_metrics = evaluation_report.get("optimal_threshold_metrics", {})
    if optimal_metrics.get("optimal_threshold"):
        print(f"\n       Optimal Threshold Analysis (F1-based):")
        print(f"       Optimal Threshold: {optimal_metrics.get('optimal_threshold')}")
        print(f"       Optimal F1 Score: {optimal_metrics.get('optimal_f1_score')}")
        print(f"       Optimal Recall: {optimal_metrics.get('optimal_recall')}")
        print(f"       Optimal Precision: {optimal_metrics.get('optimal_precision')}")
        if optimal_metrics.get("roc_auc_score"):
            print(f"       ROC AUC: {optimal_metrics.get('roc_auc_score')}")

    print("\n[8/8] Version tracking + deployment gate...")
    deploy_summary = register_and_maybe_deploy(artifacts, evaluation_report)

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(ARTIFACTS_PATH, "wb") as f:
        pickle.dump(artifacts, f)

    file_size_mb = os.path.getsize(ARTIFACTS_PATH) / (1024 * 1024)
    print(f"       Saved working artifact alias: {ARTIFACTS_PATH} ({file_size_mb:.1f} MB)")
    print(f"       Validation report: {VALIDATION_REPORT_PATH}")
    print(f"       Model registry: {MODEL_REGISTRY_PATH}")
    print(f"       Baseline metrics: {BASELINE_METRICS_PATH}")

    latest = deploy_summary.get("latest_run", {})
    if latest.get("deployed"):
        print(
            f"       DEPLOYED candidate as production model version "
            f"{latest.get('deployed_model_version')}"
        )
    else:
        print(
            f"       Candidate rejected; kept production model version "
            f"{latest.get('deployed_model_version')}"
        )

    print("\n" + "=" * 60)
    print("  Training complete!")
    print(f"  {scored} products scored | {len(alerts)} alerts generated")
    print("=" * 60)

    return artifacts


if __name__ == "__main__":
    main()
