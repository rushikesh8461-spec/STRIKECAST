#!/usr/bin/env python
"""Validate the fail-closed candidate/production acceptance record."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_EVIDENCE = (
    "real_dataset_contract_passed", "reproducible_preprocessing", "validation_evaluation_exists",
    "untouched_test_evaluation_exists", "required_rare_event_metrics_exist",
    "calibration_review_passed", "artifact_checksum_verified", "lineage_metadata_complete",
)
METADATA_FIELDS = (
    "model_name", "model_version", "dataset_version", "feature_version", "target_version",
    "training_config", "split_version", "metrics", "calibration_status", "checksum",
    "artifact_path", "created_at", "status",
)


def validate(record: dict, root: Path) -> list[str]:
    errors: list[str] = []
    if record.get("record_type") != "model_acceptance" or not record.get("record_version"):
        errors.append("record_type/model_acceptance and record_version are required")
    try:
        created = datetime.fromisoformat(str(record.get("created_at", "")).replace("Z", "+00:00"))
        if created.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("created_at must be timezone-aware ISO-8601")
    status = record.get("status")
    if status == "BLOCKED":
        if record.get("candidate") is not None:
            errors.append("BLOCKED record must not carry a candidate artifact")
        if not record.get("unmet_requirements"):
            errors.append("BLOCKED record must explain unmet requirements")
        return errors
    if status not in {"CANDIDATE", "PRODUCTION"}:
        return ["status must be BLOCKED, CANDIDATE or PRODUCTION"]

    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        return ["evidence must be an object"]
    required_evidence = BASELINE_EVIDENCE + (("production_acceptance_criteria_passed",) if status == "PRODUCTION" else ())
    errors.extend(f"evidence.{key} must be true" for key in required_evidence if evidence.get(key) is not True)
    candidate = record.get("candidate")
    if not isinstance(candidate, dict):
        return errors + ["candidate metadata object is required"]
    for field in METADATA_FIELDS:
        value = candidate.get(field)
        if value in (None, "", "NOT_AVAILABLE", {}):
            errors.append(f"candidate.{field} is missing or unavailable")
    if candidate.get("status") != status:
        errors.append("candidate.status must match acceptance record status")
    if status in {"CANDIDATE", "PRODUCTION"}:
        metrics = candidate.get("metrics")
        required_metrics = ("n", "positive_count", "brier_score", "ece", "roc_auc", "pr_auc",
                            "precision", "recall", "pod", "far", "csi", "confusion_matrix")
        if not isinstance(metrics, dict):
            errors.append("candidate.metrics must be a metric record")
        else:
            for name in required_metrics:
                if metrics.get(name) is None:
                    errors.append(f"candidate.metrics.{name} is required")
        if candidate.get("evaluation_split") != "test":
            errors.append("candidate evaluation_split must identify untouched test evaluation")
        if candidate.get("calibration_status") not in {"VALIDATED", "VALIDATED_ON_VALIDATION"}:
            errors.append("candidate calibration_status must document reviewed validation-only calibration")
    relative = candidate.get("artifact_path")
    if isinstance(relative, str):
        path = (root / relative).resolve()
        if root.resolve() not in path.parents:
            errors.append("candidate artifact path escapes the project root")
        elif not path.is_file():
            errors.append("candidate artifact does not exist")
        else:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != candidate.get("checksum"):
                errors.append("candidate artifact checksum mismatch")
    if status == "PRODUCTION" and isinstance(relative, str) and not relative.startswith("artifacts/models/production/"):
        errors.append("PRODUCTION artifacts must be inside artifacts/models/production")
    if status == "CANDIDATE" and isinstance(relative, str) and not relative.startswith("artifacts/models/candidate/"):
        errors.append("CANDIDATE artifacts must be inside artifacts/models/candidate")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=ROOT / "artifacts/models/candidate/acceptance.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"acceptance record is unreadable: {exc}")
    errors = validate(record, args.root)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"Acceptance record valid: {record['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
