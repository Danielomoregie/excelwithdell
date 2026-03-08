# High-Risk Threshold Configuration Guide

## Quick Start

The high-risk threshold controls the precision/recall trade-off of your model. **Each training run automatically tracks which threshold was used**, so you can compare different thresholds across runs without retraining.

---

## How to Adjust

### Step 1: Edit the Threshold

Open **`src/Model_Evaluation_And_Versioning.py`** and find this section (line ~21):

```python
# ==============================
# THRESHOLD CONFIGURATION
# ==============================
HIGH_RISK_THRESHOLD = 50  # Score >= this value is classified as "high risk"
```

Change the value. Future runs will use the new threshold.

**Examples:**
- `HIGH_RISK_THRESHOLD = 25` → Lower threshold = **Higher Recall** (catch more risk, more false positives)
- `HIGH_RISK_THRESHOLD = 50` → Medium threshold (current baseline)
- `HIGH_RISK_THRESHOLD = 75` → Higher threshold = **Higher Precision** (fewer false positives, miss some risk)

---

## Step 2: Run Training

```bash
python src/Train_Model.py
```

The output will show:
```
[7/8] Running manual-labeled evaluation on the 20% testing dataset...
       Validation metrics:
       High-Risk Threshold: 75 (adjust in Model_Evaluation_And_Versioning.py)
       Pearson: 0.938
       MAE: 24.8865
       Directional Accuracy: 0.62
       High-Risk Recall: 0.6000  ← New recall with threshold=75
       High-Risk Precision: 0.9583  ← New precision with threshold=75
```

---

## Step 3: Compare in Developer Console

Visit **Developer → Section 1: Model Training Results**

The version table now includes a **Threshold column** showing which threshold was used for each run:

| Run | Candidate | **Threshold** | Pearson | Recall | Precision | Directional | MAE | Deployed |
|-----|-----------|--------------|---------|--------|-----------|-------------|-----|----------|
| 0   | 0         | **50**       | 0.938   | 0.360  | 1.0       | 0.62        | 24.9| yes      |
| 1   | 1         | **75**       | 0.938   | 0.600  | 0.958     | 0.62        | 24.9| no       |

This allows you to **compare**: "At threshold 75, we gain recall without losing too much precision."

---

## Recipe: Precision ↑ Recall ↑ (Without Retraining)

1. **Run 0**: Train with `HIGH_RISK_THRESHOLD = 90`
   - Result: Recall 10%, Precision 99%
   - Decision: Too conservative (missing too much risk)

2. **Run 1**: Adjust to `HIGH_RISK_THRESHOLD = 75`
   - Result: Recall 65%, Precision 92%
   - Decision: Good balance, DEPLOY

3. **Run 2**: Try `HIGH_RISK_THRESHOLD = 50` (if you want higher recall)
   - Result: Recall 80%, Precision 88%
   - Decision: Depends on your tolerance for false alerts

---

## Key Points

✅ **No model retraining needed** — Same model weights, just different classification threshold  
✅ **Full version history** — All runs preserved, compare across thresholds  
✅ **Automatic deployment gating** — New model only deploys if composite score improves  
✅ **Threshold tracked in registry** — Each run records which threshold was used

---

## Model Evaluation & Versioning Behavior

**Step [7/8]** of training:
- Loads the 20% test set with **human-labeled severity scores** (0-100)
- Compares model predictions vs. labeled severity using the **current `HIGH_RISK_THRESHOLD`**
- Computes: Pearson, MAE, Directional Accuracy, Recall/Precision
- Writes `Validation_Report.json`

**Step [8/8]** of training:
- Reads registry and compares candidate score vs. current production score
- **Deploy only if candidate is better** (stricter than "different")
- Records threshold used in `model_registry.json`

---

## Files You'll Edit

| File | What | How Often |
|------|------|-----------|
| `src/Model_Evaluation_And_Versioning.py` | Change `HIGH_RISK_THRESHOLD` | Before each test run |
| `evaluation_reviews.csv` | Update human labels (optional) | To improve model training |

---

## FAQ

**Q: If I just change the threshold without retraining, aren't I just moving the cutoff line?**  
A: Exactly! That's the point. It's a fast way to tune precision/recall without waiting for model retraining. It shows empirically what happens at different thresholds using your actual test data.

**Q: Will the old models still exist?**  
A: Yes. Only deployed models are saved (e.g., `model_0.pkl`, `model_1.pkl`). Rejected candidates are logged in the registry but not saved as files.

**Q: What if comparing thresholds doesn't help?**  
A: That's a signal to improve the model itself — better training labels, more features, or model architecture.

---

## Next Steps

1. Run with `threshold = 50` (baseline)
2. Observe: "Recall 36%, Precision 100% — too conservative"
3. Run with `threshold = 75`
4. Observe: "Recall 65%, Precision 92% — better balance"
5. Decide: Deploy the 75 version if it meets business requirements
