#!/usr/bin/env python
"""Compare compatible baseline candidates on one validated dataset's VALIDATION split.

This entry point never selects on or reports TEST metrics. Selection policy
and final one-time TEST evaluation must be reviewed and recorded separately.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "packages"), str(ROOT / "ml/research/strikecast")]
from strikecast_core.evaluation.metrics import evaluate_binary_classifier  # noqa: E402
from src.ingestion.real_dataset import load_real_dataset  # noqa: E402
from src.models.climatology import ClimatologyBaseline  # noqa: E402
from src.models.classical_ml import ClassicalMLBaseline  # noqa: E402
from src.models.persistence import PersistenceBaseline  # noqa: E402
from src.models.tree_ml import TreeMLBaseline  # noqa: E402
from ml.training.strikecast_training.config import DataContract  # noqa: E402


def _tensor(values: np.ndarray) -> torch.Tensor:
    return torch.as_tensor(values, dtype=torch.float32)


def _probabilities(model, inputs: torch.Tensor) -> np.ndarray:
    output = model.predict(inputs).prediction.detach().cpu().numpy()
    return output.reshape(-1).astype(float)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path, help="Validated dataset directory with manifest.json and paired.npz")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "reports" / "baseline_benchmark.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = load_real_dataset(args.dataset)
    manifest, arrays = dataset.manifest, dataset.arrays
    feature_order = manifest["feature_order"]
    if "lightning_strike_count" not in feature_order:
        parser.error("persistence candidate requires lightning_strike_count in feature_order")
    x_train, x_val = _tensor(arrays["X_train"]), _tensor(arrays["X_validation"])
    y_train = _tensor(arrays["y_train"][:, :, None, :, :])
    train_observed = torch.as_tensor(arrays["target_observation_mask_train"][:, :, None, :, :], dtype=torch.bool)
    val_observed = arrays["target_observation_mask_validation"].astype(bool).reshape(-1)
    y_val_all = arrays["y_validation"].astype(np.int64).reshape(-1)
    y_val = y_val_all[val_observed]
    if len(np.unique(y_val)) != 2:
        parser.error("validation must contain both event and non-event labels")
    target_stats = manifest["normalization"]["feature_stats"]["lightning_strike_count"]
    zero_threshold = (0.0 - float(target_stats["mean"])) / float(target_stats["std"])
    _, t, c, h, w = arrays["X_train"].shape
    contract = DataContract(
        sequence_length=t, input_channels=c, height=h, width=w, forecast_horizon=1,
        target_type="binary", input_channel_names=list(feature_order),
        lightning_channel_index=feature_order.index("lightning_strike_count"),
        lightning_zero_threshold=zero_threshold,
    )
    x_val_torch = x_val
    candidates = {
        "climatology": ClimatologyBaseline(contract),
        "persistence": PersistenceBaseline(contract),
        "logistic_regression": ClassicalMLBaseline(contract, seed=args.seed),
        "histogram_gradient_boosting": TreeMLBaseline(contract, seed=args.seed),
    }
    benchmark_config = {
        "seed": args.seed,
        "candidate_names": list(candidates),
        "metric_threshold": 0.5,
        "fit_split": "train",
        "comparison_split": "validation",
    }
    benchmark_config_bytes = json.dumps(benchmark_config, sort_keys=True, separators=(",", ":")).encode()
    reports = []
    expected_prob_count = int(val_observed.sum())
    for name, model in candidates.items():
        train_seconds = 0.0
        if name == "climatology":
            started = time.perf_counter()
            model.fit(y_train, train_observed)
            train_seconds = time.perf_counter() - started
        elif name in {"logistic_regression", "histogram_gradient_boosting"}:
            started = time.perf_counter()
            model.fit(x_train, y_train, train_observed)
            train_seconds = time.perf_counter() - started
        start = time.perf_counter()
        probabilities = _probabilities(model, x_val_torch)
        inference_seconds = time.perf_counter() - start
        if len(probabilities) != int(np.prod(arrays["y_validation"].shape)):
            raise RuntimeError(f"{name} output shape does not match validation target shape")
        metrics = evaluate_binary_classifier(y_val.tolist(), probabilities[val_observed])
        reports.append({
            "candidate": name,
            "model_version": model.model_version,
            "training_config": ({
                "seed": args.seed,
                "estimator": model._estimator.__class__.__name__,
                "parameters": model._estimator.get_params(deep=False),
            } if hasattr(model, "_estimator") else {
                "fit_split": "train",
                "baseline": "per-cell event frequency" if name == "climatology" else "last observed lightning occurrence",
            }),
            "validation_metrics": metrics.to_dict(),
            "train_duration_seconds": round(train_seconds, 6),
            "validation_inference_ms_per_sample": round(inference_seconds * 1000 / len(x_val), 6),
            "model_size_bytes": "NOT_MEASURED",
            "memory_usage_bytes": "NOT_MEASURED",
        })

    report = {
        "status": "VALIDATION_BASELINE_COMPARISON_ONLY",
        "dataset_name": manifest["dataset_name"],
        "dataset_version": manifest["dataset_version"],
        "manifest_sha256": hashlib.sha256((args.dataset / "manifest.json").read_bytes()).hexdigest(),
        "dataset_payload_sha256": manifest["payload"]["sha256"],
        "feature_version": manifest["feature_version"],
        "target_version": manifest["target_version"],
        "preprocessing_version": manifest["preprocessing_version"],
        "split_version": manifest.get("split_version", "NOT_AVAILABLE"),
        "split": "validation",
        "forecast_horizon_steps": manifest["forecast_horizon"],
        "temporal_cadence_minutes": manifest["temporal_cadence_minutes"],
        "random_seed": args.seed,
        "benchmark_config": benchmark_config,
        "benchmark_config_sha256": hashlib.sha256(benchmark_config_bytes).hexdigest(),
        "validation_sample_count": int(len(x_val)),
        "prediction_cell_count": expected_prob_count,
        "unknown_validation_cell_count": int((~val_observed).sum()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidates": reports,
        "selection_status": "NO_WINNER_DECLARED",
        "selection_note": "Candidates share the same validated dataset, target, TRAIN split, VALIDATION split, feature schema, lead and metrics. Review rare-event discrimination, calibration, robustness and resource measurements together; no acceptance criteria or real-data evidence currently authorizes a winner. TEST was not used for selection or metric reporting.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
