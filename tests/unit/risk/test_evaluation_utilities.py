from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from strikecast_core.evaluation.metrics import evaluate_binary_classifier

ROOT = Path(__file__).resolve().parents[3]
LINEAGE = {"dataset_version": "unit-fixture-v1", "feature_version": "fixture-features-v1",
           "target_version": "fixture-target-v1", "split_version": "fixture-split-v1",
           "model_name": "unit-fixture", "model_version": "fixture-model-v1"}


def _prediction_file(path: Path, split: str, sample_prefix: str, n: int = 40, positive_probability: float = 0.75):
    labels = np.array([0, 1] * (n // 2), dtype=np.int64)
    probabilities = np.where(labels == 1, positive_probability, 1 - positive_probability)
    np.savez(path, y_true=labels, probabilities=probabilities,
             sample_ids=np.array([f"{sample_prefix}-{i}" for i in range(n)]),
             split=np.array(split), **LINEAGE)


def test_rare_event_metrics_include_discrimination_calibration_and_contingency():
    result = evaluate_binary_classifier([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8])
    assert result.roc_auc == 1.0
    assert result.pr_auc == 1.0
    assert result.brier_score == 0.025
    assert result.pod == 1.0 and result.far == 0.0 and result.csi == 1.0
    assert result.confusion_matrix == ((2, 0), (0, 2))
    assert result.event_frequency == 0.5


def test_auc_is_unavailable_when_labels_contain_one_class():
    result = evaluate_binary_classifier([0, 0], [0.1, 0.2])
    assert result.roc_auc is None and result.pr_auc is None


def test_evaluation_rejects_non_binary_fractional_labels():
    with pytest.raises(ValueError, match="binary"):
        evaluate_binary_classifier([0, 0.5], [0.1, 0.2])


def test_evaluate_outputs_lineage_and_rare_event_metrics(tmp_path):
    source = tmp_path / "test_predictions.npz"
    output = tmp_path / "metrics.json"
    _prediction_file(source, "test", "test")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "ml" / "evaluate.py"), "--data", str(source),
                    "--output", str(output)], check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert report["status"] == "MEASURED_ON_SUPPLIED_TEST_LABELS"
    metrics = report["metrics"]
    assert metrics["positive_count"] == 20
    assert metrics["roc_auc"] == 1.0 and metrics["pr_auc"] == 1.0
    assert "reliability_diagram_bins" in report and metrics["csi"] == 1.0


def test_evaluation_rejects_non_test_predictions(tmp_path):
    source = tmp_path / "validation_predictions.npz"
    _prediction_file(source, "validation", "validation")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "ml" / "evaluate.py"), "--data", str(source)],
                           capture_output=True, text=True)
    assert result.returncode == 2
    assert "split=test" in result.stderr


def test_calibrator_fits_validation_and_reports_untouched_test(tmp_path):
    validation = tmp_path / "validation.npz"
    test = tmp_path / "test.npz"
    output = tmp_path / "candidate.json"
    _prediction_file(validation, "validation", "validation")
    _prediction_file(test, "test", "test", positive_probability=0.68)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "ml" / "calibrate.py"), "--validation", str(validation),
                    "--test", str(test), "--output", str(output)], check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert report["fit_split"] == "validation"
    assert report["evaluation_split"] == "test"
    assert report["status"] == "CANDIDATE_NOT_ACTIVATED"
    assert report["validation_test_sample_ids_disjoint"] is True
    assert "raw_test_reliability_bins" in report and "calibrated_test_metrics" in report


def test_calibration_rejects_overlapping_validation_and_test_ids(tmp_path):
    validation = tmp_path / "validation.npz"
    test = tmp_path / "test.npz"
    _prediction_file(validation, "validation", "same")
    _prediction_file(test, "test", "same")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "ml" / "calibrate.py"),
                             "--validation", str(validation), "--test", str(test)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "sample_ids overlap" in result.stderr
