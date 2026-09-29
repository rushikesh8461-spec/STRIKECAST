from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ml/validate_model_acceptance.py"


def test_current_acceptance_record_explicitly_blocks_promotion():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True)
    assert "Acceptance record valid: BLOCKED" in result.stdout


def _candidate_record(checksum: str) -> dict:
    evidence = {
        "real_dataset_contract_passed": True,
        "reproducible_preprocessing": True,
        "validation_evaluation_exists": True,
        "untouched_test_evaluation_exists": True,
        "required_rare_event_metrics_exist": True,
        "calibration_review_passed": True,
        "artifact_checksum_verified": True,
        "lineage_metadata_complete": True,
        "production_acceptance_criteria_passed": False,
    }
    metrics = {key: 0.5 for key in (
        "brier_score", "ece", "roc_auc", "pr_auc", "precision", "recall", "pod", "far", "csi"
    )}
    metrics.update({"n": 100, "positive_count": 10, "confusion_matrix": [[80, 10], [5, 5]]})
    return {
        "record_type": "model_acceptance", "record_version": "1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "CANDIDATE",
        "evidence": evidence,
        "candidate": {
            "model_name": "fixture-model", "model_version": "fixture-v1",
            "dataset_version": "fixture-data-v1", "feature_version": "fixture-features-v1",
            "target_version": "fixture-target-v1", "training_config": {"seed": 7},
            "split_version": "fixture-split-v1", "metrics": metrics,
            "calibration_status": "VALIDATED_ON_VALIDATION", "checksum": checksum,
            "artifact_path": "artifacts/models/candidate/model.bin", "created_at": "2026-01-01T00:00:00Z",
            "status": "CANDIDATE", "evaluation_split": "test",
        },
    }


def test_acceptance_rejects_artifact_checksum_mismatch(tmp_path):
    artifact = tmp_path / "artifacts/models/candidate/model.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fixture artifact")
    record_path = tmp_path / "acceptance.json"
    record_path.write_text(json.dumps(_candidate_record("0" * 64)), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--record", str(record_path), "--root", str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "checksum mismatch" in result.stdout


def test_acceptance_accepts_candidate_only_with_complete_declared_gates(tmp_path):
    artifact = tmp_path / "artifacts/models/candidate/model.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fixture artifact")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    record_path = tmp_path / "acceptance.json"
    record_path.write_text(json.dumps(_candidate_record(digest)), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--record", str(record_path), "--root", str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert "Acceptance record valid: CANDIDATE" in result.stdout
