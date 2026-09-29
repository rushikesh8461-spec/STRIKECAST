#!/usr/bin/env python
"""Evaluate one provenance-bearing, untouched TEST prediction archive."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
from strikecast_core.evaluation.metrics import evaluate_binary_classifier  # noqa: E402


LINEAGE_FIELDS = ("dataset_version", "feature_version", "target_version", "split_version", "model_name", "model_version")


def _metadata_scalar(payload, key: str) -> str:
    if key not in payload.files:
        raise ValueError(f"prediction archive requires {key}")
    value = np.asarray(payload[key])
    if value.size != 1:
        raise ValueError(f"{key} must be a scalar")
    result = str(value.item()).strip()
    if not result or result.upper() == "NOT_AVAILABLE":
        raise ValueError(f"{key} must contain a known provenance value")
    return result


def _reliability_bins(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    result = []
    for index in range(n_bins):
        lower, upper = index / n_bins, (index + 1) / n_bins
        mask = (p >= lower) & ((p < upper) | ((index == n_bins - 1) & (p == 1)))
        if mask.any():
            result.append({"lower": lower, "upper": upper, "count": int(mask.sum()),
                           "mean_probability": float(p[mask].mean()),
                           "observed_frequency": float(y[mask].mean())})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path,
                        help="NPZ y_true/probabilities/sample_ids plus split=test and dataset/model lineage fields")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "metrics" / "model_comparison.json")
    args = parser.parse_args()
    try:
        with np.load(args.data, allow_pickle=False) as payload:
            required = {"y_true", "probabilities", "sample_ids", "split", *LINEAGE_FIELDS}
            missing = required - set(payload.files)
            if missing:
                raise ValueError(f"prediction archive missing fields: {', '.join(sorted(missing))}")
            metadata = {field: _metadata_scalar(payload, field) for field in LINEAGE_FIELDS}
            if _metadata_scalar(payload, "split") != "test":
                raise ValueError("evaluation input must be explicitly marked split=test")
            y = np.asarray(payload["y_true"]).reshape(-1)
            probabilities = np.asarray(payload["probabilities"], dtype=float).reshape(-1)
            sample_ids = np.asarray(payload["sample_ids"]).reshape(-1).astype(str)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    if len(y) == 0 or len(y) != len(probabilities) or len(y) != len(sample_ids):
        parser.error("labels, probabilities and sample_ids must be non-empty and aligned")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        parser.error("test arrays must contain binary labels and finite probabilities in [0, 1]")
    if len(set(sample_ids.tolist())) != len(sample_ids):
        parser.error("test sample_ids must be unique")
    if len(np.unique(y)) != 2:
        parser.error("test labels must contain both event and non-event cases for a valid report")

    metrics = evaluate_binary_classifier(y.astype(int).tolist(), probabilities.tolist())
    result = {
        "status": "MEASURED_ON_SUPPLIED_TEST_LABELS",
        **metadata,
        "split": "test",
        "prediction_archive_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "metrics": metrics.to_dict(),
        "reliability_diagram_bins": _reliability_bins(y.astype(int), probabilities),
        "caveat": "Metrics describe only the supplied TEST archive. This utility does not independently verify source labels, split construction, or model lineage.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report = args.output.parent.parent / "reports" / "model_comparison.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Model evaluation\n\n" + "\n".join(
        f"- {key}: {value}" for key, value in result.items()
    ) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
