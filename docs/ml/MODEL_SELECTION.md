# Model selection protocol

Current status: `BLOCKED — REAL DATA REQUIRED`. There is no selected candidate, winner, or observational benchmark. The bundled model remains `DEMO_ONLY`.

## Runnable comparison interface

After a real paired dataset passes [`DATASET_CONTRACT.md`](../data/DATASET_CONTRACT.md), run from the repository root:

```powershell
python scripts/ml/benchmark.py --dataset <validated-dataset-directory> --output artifacts/reports/baseline_benchmark.json --seed 42
```

The entry point validates the same dataset manifest, fits each fitted candidate on TRAIN only, and measures each on VALIDATION only using identical examples, target, feature order, selected lead, and metrics. It currently compares train-period per-cell climatology, last-observed lightning persistence, logistic regression, and histogram gradient boosting. It records validation rare-event metrics and measured training/inference time. Model size and memory are explicitly marked `NOT_MEASURED`. It does not read test labels for metrics, select a winner, save a model, calibrate, or activate an artifact. Test data must remain untouched until the validation review and acceptance protocol are fixed.

The persistence baseline requires the `lightning_strike_count` feature and its zero value after the TRAIN-fitted scaler. It fails closed if the M2 channel name/scaler is unavailable; it must not treat arbitrary channel 0 (currently brightness temperature) as lightning.

Research ConvLSTM and fusion models exist and have synthetic shape/training tests, but there is no real-data benchmark/training adapter for them yet. Add them to a future comparison only when they can consume the same validated split without test reuse. XGBoost/LightGBM are not installed candidates. No tree family beyond the implemented histogram-gradient-boosting baseline is claimed.

## Review and selection

Review PR-AUC and ROC-AUC with event frequency, Brier score and ECE, thresholded precision/recall/POD/FAR/CSI and confusion matrix; also assess seasonal/geographic/lead robustness, uncertainty, reproducibility, training/inference cost, model size and memory. The benchmark deliberately emits `NO_WINNER_DECLARED`: project owners have not approved numerical acceptance criteria, and this workspace has no real data to apply them to. Never rank by training score or one metric alone.
