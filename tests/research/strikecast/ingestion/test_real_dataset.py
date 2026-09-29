import hashlib
import json
from datetime import datetime, timedelta, timezone
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.ingestion.real_dataset import DatasetContractError, REQUIRED_GATES, load_real_dataset


def _manifest(payload_checksum):
    provider = {
        "source": "verified-source", "provider": "provider-name", "license": "CC-BY-4.0",
        "coverage": {"kind": "documented"}, "cadence_minutes": 15,
        "spatial_resolution_deg": 1.0, "variables": ["temperature"], "units": ["K"],
        "time_range": ["2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"],
        "geographic_range": {"lat": [-10, 10], "lon": [20, 30]},
        "checksum": payload_checksum, "dataset_version": "v1",
    }
    return {
        "dataset_name": "test-paired-fixture",
        "dataset_version": "v1", "split_version": "test-chronological-v1",
        "quality_thresholds": {"max_missing_fraction": 0.1},
        "feature_order": ["temperature", "cape", "lightning_strike_count"],
        "feature_version": "test-features-v1", "target_version": "lightning_occurrence_at_horizon_v1",
        "preprocessing_version": "test-preprocess-v1", "created_at": "2026-01-04T00:00:00Z",
        "collection_period": ["2026-01-01T00:00:00Z", "2026-01-01T06:00:00Z"],
        "geographic_region": "test-fixture-region",
        "missing_value_policy": "raw: reject_or_quarantine; prepared: train_mean_fill_with_valid_mask",
        "feature_units": {"temperature": "K", "cape": "J/kg", "lightning_strike_count": "count"},
        "target_definition": "binary lightning occurrence in each target grid cell exactly one 15-minute cadence step after the final input timestep", "forecast_horizon": 1,
        "temporal_cadence_minutes": 15,
        "spatial_grid": {"lat_min": 0.0, "lat_max": 1.0, "lon_min": 20.0, "lon_max": 21.0,
                         "latitude_resolution_deg": 1.0, "longitude_resolution_deg": 1.0,
                         "n_lat": 2, "n_lon": 2},
        "normalization": {"method": "z-score", "fit_split": "train",
                          "feature_stats": {"temperature": {"mean": 0, "std": 1}, "cape": {"mean": 0, "std": 1},
                                            "lightning_strike_count": {"mean": 0, "std": 1}},
                          "fit_time_range": ["2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"]},
        "leakage_protocol": {"normalization_fit_split": "train", "calibration_fit_split": "validation",
                             "threshold_selection_split": "validation", "model_selection_split": "validation",
                             "final_evaluation_split": "test"},
        "quality_gates": {k: True for k in REQUIRED_GATES},
        "providers": {"atmospheric": provider, "lightning": dict(provider)},
        "payload": {"file": "paired.npz", "sha256": payload_checksum},
    }


def _write_dataset(root, corrupt_target_time=False):
    root.mkdir()
    arrays = {"latitudes": np.array([0., 1.]), "longitudes": np.array([20., 21.])}
    for index, split in enumerate(("train", "validation", "test")):
        base_step = index * 10
        arrays[f"X_{split}"] = np.zeros((1, 2, 3, 2, 2), dtype=np.float32)
        labels = np.array([[[[0, 1], [0, 1]]]], dtype=np.float32)
        arrays[f"y_{split}"] = labels
        arrays[f"target_observation_mask_{split}"] = np.ones(labels.shape, dtype=bool)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=base_step * 15)
        inputs = [base + timedelta(minutes=offset * 15) for offset in (0, 1)]
        target = base + timedelta(minutes=(1 if corrupt_target_time and split == "train" else 2) * 15)
        arrays[f"timestamps_{split}"] = np.array([[t.isoformat().replace("+00:00", "Z") for t in inputs]])
        arrays[f"target_timestamps_{split}"] = np.array([[target.isoformat().replace("+00:00", "Z")]])
        arrays[f"availability_timestamps_{split}"] = np.array([[
            [t.isoformat().replace("+00:00", "Z")] * 3 for t in inputs
        ]])
        arrays[f"valid_mask_{split}"] = np.ones((1, 2, 3, 2, 2), dtype=bool)
    np.savez_compressed(root / "paired.npz", **arrays)
    checksum = hashlib.sha256((root / "paired.npz").read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(_manifest(checksum)), encoding="utf-8")


def _rewrite_payload(folder, arrays):
    np.savez_compressed(folder / "paired.npz", **arrays)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["payload"]["sha256"] = hashlib.sha256((folder / "paired.npz").read_bytes()).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_real_dataset_requires_complete_provenance_and_valid_chronology(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    dataset = load_real_dataset(folder)
    assert dataset.arrays["X_train"].shape == (1, 2, 3, 2, 2)
    assert dataset.arrays["y_test"].shape == (1, 1, 2, 2)


def test_real_dataset_rejects_missing_license(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    del manifest["providers"]["lightning"]["license"]
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DatasetContractError, match="license"):
        load_real_dataset(folder)


def test_real_dataset_rejects_changed_payload_checksum(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    with (folder / "paired.npz").open("ab") as f:
        f.write(b"modified")
    with pytest.raises(DatasetContractError, match="SHA-256"):
        load_real_dataset(folder)


def test_real_dataset_rejects_target_time_leakage(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder, corrupt_target_time=True)
    with pytest.raises(DatasetContractError, match="strictly after"):
        load_real_dataset(folder)


def test_real_dataset_rejects_failed_quality_gate(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["quality_gates"]["no_future_leakage"] = False
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DatasetContractError, match="Quality gates failed"):
        load_real_dataset(folder)


def test_real_dataset_requires_observed_positive_and_negative_labels(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    with np.load(folder / "paired.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    # Hide every positive target. Its stored zero placeholders must not be
    # counted as observed negatives to satisfy the class-balance gate.
    arrays["target_observation_mask_test"][:, :, 0, 1] = False
    arrays["target_observation_mask_test"][:, :, 1, 1] = False
    _rewrite_payload(folder, arrays)
    with pytest.raises(DatasetContractError, match="both event and non-event labels"):
        load_real_dataset(folder)


def test_real_dataset_requires_target_observation_mask(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    with np.load(folder / "paired.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files if key != "target_observation_mask_test"}
    _rewrite_payload(folder, arrays)
    with pytest.raises(DatasetContractError, match="target_observation_mask_test"):
        load_real_dataset(folder)


def test_real_dataset_rejects_test_set_calibration(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["leakage_protocol"]["calibration_fit_split"] = "test"
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DatasetContractError, match="Leakage protocol"):
        load_real_dataset(folder)


def test_real_dataset_requires_versioned_provenance(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["feature_version"] = "NOT_AVAILABLE"
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DatasetContractError, match="feature_version is unavailable"):
        load_real_dataset(folder)


def test_real_dataset_rejects_feature_unavailable_at_forecast_issue(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    with np.load(folder / "paired.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    arrays["availability_timestamps_train"][0, 0, 0] = "2026-01-01T00:45:00Z"
    _rewrite_payload(folder, arrays)
    with pytest.raises(DatasetContractError, match="unavailable at forecast issue time"):
        load_real_dataset(folder)


def test_real_dataset_rejects_coordinate_grid_metadata_mismatch(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["spatial_grid"]["latitude_resolution_deg"] = 0.5
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DatasetContractError, match="do not match spatial_grid"):
        load_real_dataset(folder)


def test_real_dataset_rejects_duplicate_or_shuffled_samples_inside_split(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    with np.load(folder / "paired.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    for key in ("X_train", "y_train", "timestamps_train", "target_timestamps_train",
                "availability_timestamps_train", "valid_mask_train", "target_observation_mask_train"):
        arrays[key] = np.concatenate([arrays[key], arrays[key]], axis=0)
    _rewrite_payload(folder, arrays)
    with pytest.raises(DatasetContractError, match="shuffled or duplicated"):
        load_real_dataset(folder)


def test_baseline_benchmark_uses_shared_validated_splits_and_leaves_test_unreported(tmp_path):
    folder = tmp_path / "paired"
    _write_dataset(folder)
    output = tmp_path / "baseline_benchmark.json"
    script = Path(__file__).resolve().parents[4] / "scripts" / "ml" / "benchmark.py"
    with np.load(folder / "paired.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    arrays["target_observation_mask_validation"][:, :, 1, :] = False
    _rewrite_payload(folder, arrays)
    subprocess.run([sys.executable, str(script), "--dataset", str(folder), "--output", str(output), "--seed", "11"],
                   check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert report["status"] == "VALIDATION_BASELINE_COMPARISON_ONLY"
    assert {row["candidate"] for row in report["candidates"]} == {
        "climatology", "persistence", "logistic_regression", "histogram_gradient_boosting"
    }
    assert all(row["validation_metrics"]["n"] == 2 for row in report["candidates"])
    assert report["unknown_validation_cell_count"] == 2
    assert report["selection_status"] == "NO_WINNER_DECLARED"
    assert all("test_metrics" not in row for row in report["candidates"])
