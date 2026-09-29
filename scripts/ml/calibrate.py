#!/usr/bin/env python
"""Fit Platt scaling on VALIDATION and report once on untouched TEST predictions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
from strikecast_core.evaluation.metrics import evaluate_binary_classifier  # noqa: E402

LINEAGE_FIELDS = ("dataset_version", "feature_version", "target_version", "split_version", "model_name", "model_version")


def _load(path: Path, expected_split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, str]]:
    with np.load(path, allow_pickle=False) as payload:
        required = {"y_true", "probabilities", "sample_ids", "split", *LINEAGE_FIELDS}
        missing = required - set(payload.files)
        if missing:
            raise ValueError(f"{path}: missing required fields: {', '.join(sorted(missing))}")
        metadata = {}
        for field in ("split", *LINEAGE_FIELDS):
            value = np.asarray(payload[field])
            if value.size != 1:
                raise ValueError(f"{path}: {field} must be scalar")
            metadata[field] = str(value.item()).strip()
            if not metadata[field] or metadata[field].upper() == "NOT_AVAILABLE":
                raise ValueError(f"{path}: {field} must be known")
        if metadata["split"] != expected_split:
            raise ValueError(f"{path}: expected split={expected_split}, got {metadata['split']}")
        y = np.asarray(payload["y_true"]).reshape(-1)
        p = np.asarray(payload["probabilities"], dtype=float).reshape(-1)
        sample_ids = np.asarray(payload["sample_ids"]).reshape(-1).astype(str)
    if len(y) == 0 or len(y) != len(p) or len(y) != len(sample_ids):
        raise ValueError(f"{path}: labels, probabilities and sample_ids must be non-empty and aligned")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError(f"{path}: labels must be binary and probabilities finite in [0, 1]")
    if len(set(sample_ids.tolist())) != len(sample_ids):
        raise ValueError(f"{path}: sample_ids must be unique within a split")
    if len(np.unique(y)) != 2:
        raise ValueError(f"{path}: both event and non-event labels are required")
    return y.astype(int), p, sample_ids, metadata


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
    parser.add_argument("--validation", required=True, type=Path, help="Provenance-bearing VALIDATION predictions NPZ")
    parser.add_argument("--test", required=True, type=Path, help="Untouched, provenance-bearing TEST predictions NPZ")
    parser.add_argument("--output", type=Path, default=Path("artifacts/calibration/candidate.json"))
    args = parser.parse_args()
    try:
        y_val, p_val, ids_val, meta_val = _load(args.validation, "validation")
        y_test, p_test, ids_test, meta_test = _load(args.test, "test")
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    if any(meta_val[key] != meta_test[key] for key in LINEAGE_FIELDS):
        parser.error("validation/test prediction lineage must match exactly")
    if set(ids_val.tolist()) & set(ids_test.tolist()):
        parser.error("validation and test sample_ids overlap")
    if len(y_val) < 20:
        parser.error("validation calibration needs at least 20 samples")

    logits_val = np.log(np.clip(p_val, 1e-6, 1 - 1e-6) / np.clip(1 - p_val, 1e-6, 1))
    logits_test = np.log(np.clip(p_test, 1e-6, 1 - 1e-6) / np.clip(1 - p_test, 1e-6, 1))
    calibrator = LogisticRegression(random_state=0).fit(logits_val.reshape(-1, 1), y_val)
    calibrated_test = calibrator.predict_proba(logits_test.reshape(-1, 1))[:, 1]
    raw_metrics = evaluate_binary_classifier(y_test.tolist(), p_test.tolist())
    calibrated_metrics = evaluate_binary_classifier(y_test.tolist(), calibrated_test.tolist())
    result = {
        "status": "CANDIDATE_NOT_ACTIVATED",
        **{key: meta_val[key] for key in LINEAGE_FIELDS},
        "fit_split": "validation",
        "evaluation_split": "test",
        "validation_archive_sha256": hashlib.sha256(args.validation.read_bytes()).hexdigest(),
        "test_archive_sha256": hashlib.sha256(args.test.read_bytes()).hexdigest(),
        "validation_sample_count": int(len(y_val)),
        "test_sample_count": int(len(y_test)),
        "validation_test_sample_ids_disjoint": True,
        "method": "Platt scaling",
        "fit_parameters": {"intercept": float(calibrator.intercept_[0]), "coefficient": float(calibrator.coef_[0][0])},
        "raw_test_metrics": raw_metrics.to_dict(),
        "calibrated_test_metrics": calibrated_metrics.to_dict(),
        "raw_test_reliability_bins": _reliability_bins(y_test, p_test),
        "calibrated_test_reliability_bins": _reliability_bins(y_test, calibrated_test),
        "calibration_status": "CANDIDATE_REQUIRES_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Fit used validation predictions only. Test metrics are reported once; this candidate is not activated. Prediction lineage fields and sample IDs are caller-supplied and still require provenance review.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
