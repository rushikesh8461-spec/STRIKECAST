# Evaluation protocol

Current status: `NOT_ESTABLISHED`. No real labeled held-out predictions are present. Do not report forecast metrics from the synthetic demo or bundled mock data.

`packages/strikecast_core/evaluation/metrics.py` computes Brier score, ROC-AUC, average-precision PR-AUC, ECE, event frequency/count, accuracy, precision, recall/POD, F1, FAR, CSI, and a 2×2 confusion matrix at a declared threshold. ROC-AUC and PR-AUC are unavailable (`null`) when only one label class is supplied; the final evaluation CLI rejects one-class TEST data entirely.

For a provenance-bearing prediction archive marked `split=test`, run:

```powershell
python scripts/ml/evaluate.py --data <test-predictions.npz> --output artifacts/metrics/test-evaluation.json
```

The NPZ must include aligned `y_true`, `probabilities`, unique `sample_ids`, `split="test"`, and non-placeholder `dataset_version`, `feature_version`, `target_version`, `split_version`, `model_name`, and `model_version`. The output records its input SHA-256 and reliability-bin data. These fields are caller supplied; the utility does not independently prove label quality, chronological split construction, or lineage. Validate the data contract and preserve the manifest/config/model artifacts alongside results.

Do not use TEST for candidate/model/threshold/calibrator selection. Report test results once for the frozen selected pipeline; include positive count/frequency, threshold, contingency table, uncertainty and appropriate time/region/lead slices. If labels or split provenance do not meet the contract, the result is `BLOCKED — REAL DATA REQUIRED`, not a set of substitute synthetic metrics.
