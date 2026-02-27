"""
AI Product Risk Engine — Historical Revenue Impact Replay.
Run: streamlit run ml_pipeline/app.py
"""
import streamlit as st
import pandas as pd
import pickle
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml_pipeline.database.loader import load_data
from ml_pipeline.features.engineer import build_features
from ml_pipeline.features.labels import compute_labels
from ml_pipeline.models.trainer import train_models, temporal_split, _get_feature_cols
from ml_pipeline.utils.config import OUTPUT_DIR, ensure_output_dir, TRAIN_FRAC
from ml_pipeline.utils.revenue import add_revenue_exposure
from ml_pipeline.validation.replay import run_visual_replay

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

st.set_page_config(page_title="Product Risk Engine", page_icon="⚠️", layout="wide")

with st.sidebar:
    st.subheader("Settings")
    data_source = st.radio("Data", ["CSV", "Neon SQL"], index=0)
    run_train = st.button("Train Model", use_container_width=True)
    st.divider()
    st.subheader("Replay Controls")
    risk_thresh = st.slider("Alert threshold", 0.2, 0.8, 0.5, 0.05)
    recovery_rate = st.slider("Recovery rate", 0.2, 0.6, 0.4, 0.05)

if run_train:
    ensure_output_dir()
    with st.spinner("Training..."):
        try:
            df = load_data(source="csv" if data_source == "CSV" else "neon")
            agg = build_features(df)
            agg = compute_labels(agg)
            train_df, test_df = temporal_split(agg, train_frac=TRAIN_FRAC)
            feature_cols = _get_feature_cols(agg)
            results, _, _, _ = train_models(train_df, test_df, OUTPUT_DIR)
            best_name = "xgboost" if HAS_XGB and results.get("xgboost") else "logistic_regression"
            best = results[best_name]
            with open(OUTPUT_DIR / "trained_model.pkl", "wb") as f:
                pickle.dump({"model": best["model"], "scaler": best.get("scaler"), "feature_cols": feature_cols, "model_name": best_name}, f)
            pred_df = test_df[["asin", "month", "month_dt", "risk_event"]].copy()
            X = test_df[feature_cols].fillna(0).replace([float("inf"), float("-inf")], 0)
            if best.get("scaler"):
                X = best["scaler"].transform(X)
            pred_df["risk_probability"] = best["model"].predict_proba(X)[:, 1]
            pred_df = add_revenue_exposure(pred_df)
            pred_df.to_csv(OUTPUT_DIR / "monthly_risk_predictions.csv", index=False)
            st.success("Done.")
        except Exception as e:
            st.error(str(e))

st.title("Historical Revenue Impact Replay")
st.caption("1) Find product with sharp drop → 2) Copy to post-2020 → 3) Compare model vs manual")

model_path = OUTPUT_DIR / "trained_model.pkl"
if not model_path.exists():
    st.info("Train the model first (sidebar).")
    st.stop()

with open(model_path, "rb") as f:
    bundle = pickle.load(f)

try:
    df = load_data(source="csv" if data_source == "CSV" else "neon")
except Exception:
    df = load_data(source="csv")

agg = build_features(df)
agg = compute_labels(agg)
result = run_visual_replay(df, agg, bundle["model"], bundle["scaler"], bundle["feature_cols"], risk_threshold=risk_thresh, recovery_rate=recovery_rate)

orig = result["original"]
replay = result.get("replay_series", [])

# Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Product", orig.get("product") or "—")
col2.metric("Manual took", f"{orig.get('manual_months', 0)} months" if orig.get("manual_months") else "—")
col3.metric("Model alert", result.get("model_alert") or "—")
col4.metric("Manual (est.)", result.get("manual_month") or "—")

col5, col6 = st.columns(2)
col5.metric("Months saved", f"{result.get('months_saved', 0)} months")
col6.metric("Revenue saved", f"${result.get('revenue_saved', 0)/1e6:.2f}M")

# Explanation
st.markdown("---")
st.markdown(
    f"**Logic:** Product **{orig.get('product', '—')}** had a sharp rating drop in **{orig.get('drop_month', '—')}** "
    f"and healed in **{orig.get('heal_month', '—')}**. Manual took **{orig.get('manual_months', 0)}** months to fix. "
    f"We **copied that exact data** and shifted dates to post-2020 (training ends ~2020). "
    f"Model flagged at **{result.get('model_alert') or '—'}**, manual would have at **{result.get('manual_month', '—')}**. "
    f"**{result.get('months_saved', 0)} months faster** → **${result.get('revenue_saved', 0)/1e6:.2f}M** revenue saved."
)
st.markdown("---")

try:
    import altair as alt
except ImportError:
    alt = None

# Chart 1: Original incident
st.subheader("Original incident — product trend")
st.caption("Drop (orange) and heal (red). Manual took X months between them.")
if orig.get("series"):
    df1 = pd.DataFrame(orig["series"])
    df1["month_dt"] = pd.to_datetime(df1["month_dt"])
    base1 = alt.Chart(df1).encode(x=alt.X("month_dt:T", title="Month"))
    line1a = base1.mark_line(point=True, color="#1f77b4").encode(y=alt.Y("review_count:Q", title="Review count"))
    line1b = base1.mark_line(point=True, color="#ff7f0e").encode(y=alt.Y("avg_rating:Q", title="Avg rating"))
    layers1 = [line1a, line1b]
    if orig.get("drop_month"):
        layers1.append(alt.Chart(pd.DataFrame([{"x": pd.Timestamp(orig["drop_month"] + "-01")}])).mark_rule(color="#9467bd", strokeWidth=2).encode(x="x:T"))
    if orig.get("heal_month"):
        layers1.append(alt.Chart(pd.DataFrame([{"x": pd.Timestamp(orig["heal_month"] + "-01")}])).mark_rule(color="#d62728", strokeWidth=2).encode(x="x:T"))
    if alt:
        st.altair_chart(alt.layer(*layers1).resolve_scale(y="independent").properties(height=240), use_container_width=True)
    else:
        st.line_chart(df1.set_index("month_dt")[["review_count", "avg_rating"]], height=240)
    st.markdown(f"**Purple** = drop | **Red** = heal | **Manual:** {orig.get('manual_months', 0)} months between them")
else:
    st.info("No product with sharp drop found. Try a larger dataset or looser drop threshold.")

# Chart 2: Post-2020 replay
st.subheader("Post-2020 — copied data, model vs manual")
st.caption("Same product data, dates shifted to 2020. Green = model alert, Red = when manual would act.")
if replay:
    df2 = pd.DataFrame(replay)
    df2["month_dt"] = pd.to_datetime(df2["month_dt"])
    base2 = alt.Chart(df2).encode(x=alt.X("month_dt:T", title="Month"))
    line2 = base2.mark_line(point=True, color="#1f77b4").encode(y=alt.Y("risk_prob:Q", title="Risk prob", scale=alt.Scale(domain=[0, 1])))
    layers2 = [line2]
    if result.get("model_alert"):
        layers2.append(alt.Chart(pd.DataFrame([{"x": pd.Timestamp(result["model_alert"] + "-01")}])).mark_rule(color="#2ca02c", strokeWidth=2).encode(x="x:T"))
    if result.get("manual_month"):
        layers2.append(alt.Chart(pd.DataFrame([{"x": pd.Timestamp(result["manual_month"] + "-01")}])).mark_rule(color="#d62728", strokeWidth=2).encode(x="x:T"))
    if alt:
        st.altair_chart(alt.layer(*layers2).properties(height=240), use_container_width=True)
    else:
        st.line_chart(df2.set_index("month_dt")[["risk_prob"]], height=240)
else:
    st.info("No replay data.")
