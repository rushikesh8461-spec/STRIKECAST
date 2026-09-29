"""Fail-closed loader for provenance-bearing paired atmospheric/lightning arrays.

Dataset directory format: manifest.json plus one non-pickled NPZ file named
by the manifest. This boundary is for real-data preparation; demo data is not
accepted because required license/provider metadata is absent.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np


REQUIRED_GATES = {
    "duplicate_timestamps", "monotonic_timestamps", "no_future_leakage",
    "coordinate_bounds", "physical_range_checks", "missing_data_fraction",
    "spatial_coverage", "temporal_coverage", "label_coverage", "class_balance",
    "feature_availability", "normalization_train_only", "calibration_validation_only",
    "threshold_selection_validation_only", "model_selection_validation_only",
    "test_reserved_for_final_evaluation",
}
REQUIRED_PROVIDER_FIELDS = {
    "source", "provider", "license", "coverage", "cadence_minutes",
    "spatial_resolution_deg", "variables", "units", "time_range",
    "geographic_range", "checksum", "dataset_version",
}
SPLITS = ("train", "validation", "test")
TARGET_VERSION = "lightning_occurrence_at_horizon_v1"
MISSING_VALUE_POLICY = "raw: reject_or_quarantine; prepared: train_mean_fill_with_valid_mask"


class DatasetContractError(ValueError):
    """Dataset or provenance failed a mandatory training gate."""


@dataclass(frozen=True)
class RealDataset:
    arrays: dict[str, np.ndarray]
    manifest: dict


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise DatasetContractError(f"Invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise DatasetContractError("All timestamps must include a timezone.")
    return parsed


def _required(obj: dict, keys: set[str], where: str) -> None:
    missing = sorted(k for k in keys if obj.get(k) in (None, "", [], {}))
    if missing:
        raise DatasetContractError(f"{where} missing required provenance: {', '.join(missing)}")


def load_real_dataset(dataset_dir: str | Path) -> RealDataset:
    root = Path(dataset_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise DatasetContractError("manifest.json is required")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetContractError("manifest.json is unreadable or invalid JSON") from exc

    _required(manifest, {"dataset_name", "dataset_version", "split_version", "collection_period", "geographic_region",
                         "feature_version", "target_version", "preprocessing_version", "created_at",
                         "missing_value_policy", "quality_thresholds", "feature_order", "feature_units", "target_definition",
                         "forecast_horizon", "temporal_cadence_minutes", "spatial_grid",
                         "normalization", "quality_gates", "providers", "payload", "leakage_protocol"}, "manifest")
    unavailable = {"", "NOT_AVAILABLE", "UNKNOWN", "null", "none"}
    for key in ("dataset_name", "dataset_version", "split_version", "geographic_region", "feature_version",
                "target_version", "preprocessing_version", "missing_value_policy"):
        if str(manifest[key]).strip() in unavailable:
            raise DatasetContractError(f"manifest.{key} is unavailable; provenance-complete data is required")
    if manifest["target_version"] != TARGET_VERSION:
        raise DatasetContractError(f"target_version must be {TARGET_VERSION}")
    if manifest["missing_value_policy"] != MISSING_VALUE_POLICY:
        raise DatasetContractError("missing_value_policy does not match the canonical masked train-mean-fill policy")
    created_at = _parse_utc(manifest["created_at"])
    collection_period = manifest["collection_period"]
    if not isinstance(collection_period, list) or len(collection_period) != 2:
        raise DatasetContractError("collection_period must be ordered UTC [start, end]")
    collection_start, collection_end = (_parse_utc(value) for value in collection_period)
    if collection_start >= collection_end or collection_end > created_at:
        raise DatasetContractError("collection_period must be ordered and cannot end after manifest creation")
    try:
        max_missing_fraction = float(manifest["quality_thresholds"]["max_missing_fraction"])
        if not 0 <= max_missing_fraction < 1:
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetContractError("quality_thresholds.max_missing_fraction must be in [0, 1)") from exc
    protocol = manifest["leakage_protocol"]
    required_protocol = {"normalization_fit_split": "train", "calibration_fit_split": "validation",
                         "threshold_selection_split": "validation", "model_selection_split": "validation",
                         "final_evaluation_split": "test"}
    if any(protocol.get(key) != value for key, value in required_protocol.items()):
        raise DatasetContractError("Leakage protocol must fit normalization on train, tune on validation, and reserve test for final evaluation")
    cadence = float(manifest["temporal_cadence_minutes"])
    horizon = int(manifest["forecast_horizon"])
    if cadence <= 0 or horizon < 1:
        raise DatasetContractError("Temporal cadence and forecast horizon must be positive")
    providers = manifest["providers"]
    if not isinstance(providers, dict) or not {"atmospheric", "lightning"}.issubset(providers):
        raise DatasetContractError("providers must include atmospheric and lightning metadata")
    for name in ("atmospheric", "lightning"):
        _required(providers[name], REQUIRED_PROVIDER_FIELDS, f"providers.{name}")
        for key in ("source", "provider", "license", "dataset_version"):
            if str(providers[name][key]).strip() in unavailable:
                raise DatasetContractError(f"providers.{name}.{key} is unavailable; provenance-complete data is required")
    _required(manifest["payload"], {"file", "sha256"}, "payload")
    gates = manifest["quality_gates"]
    if not isinstance(gates, dict) or REQUIRED_GATES - gates.keys():
        missing = sorted(REQUIRED_GATES - gates.keys()) if isinstance(gates, dict) else sorted(REQUIRED_GATES)
        raise DatasetContractError(f"quality_gates missing: {', '.join(missing)}")
    failed = sorted(name for name in REQUIRED_GATES if gates[name] is not True)
    if failed:
        raise DatasetContractError(f"Quality gates failed: {', '.join(failed)}")
    if not isinstance(manifest["feature_order"], list) or not manifest["feature_order"]:
        raise DatasetContractError("feature_order must be a non-empty ordered list")
    if len(manifest["feature_order"]) != len(set(manifest["feature_order"])):
        raise DatasetContractError("feature_order contains duplicates")
    if set(manifest["feature_order"]) != set(manifest["feature_units"]):
        raise DatasetContractError("feature_units must define every feature exactly once")
    normalization = manifest["normalization"]
    _required(normalization, {"method", "fit_split", "feature_stats", "fit_time_range"}, "normalization")
    if normalization["fit_split"] != "train" or protocol["normalization_fit_split"] != "train":
        raise DatasetContractError("Normalization statistics must be fitted only on train timestamps")
    if normalization["method"] != "z-score":
        raise DatasetContractError("Only the declared train-only z-score normalization is supported")
    if not isinstance(normalization["feature_stats"], dict) or set(normalization["feature_stats"]) != set(manifest["feature_order"]):
        raise DatasetContractError("Normalization statistics must cover the exact ordered feature set")
    for feature, stats in normalization["feature_stats"].items():
        try:
            mean, std = float(stats["mean"]), float(stats["std"])
            if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetContractError(f"Invalid train-only normalization statistics for feature {feature}") from exc
    if not isinstance(normalization["fit_time_range"], list) or len(normalization["fit_time_range"]) != 2:
        raise DatasetContractError("Normalization fit_time_range must document the train-only interval")
    _parse_utc(normalization["fit_time_range"][0])
    _parse_utc(normalization["fit_time_range"][1])

    payload_name = manifest["payload"]["file"]
    payload_path = (root / payload_name).resolve()
    if payload_path.parent != root or not payload_path.is_file():
        raise DatasetContractError("payload file must exist directly inside dataset directory")
    digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(manifest["payload"]["sha256"])) or digest.lower() != str(manifest["payload"]["sha256"]).lower():
        raise DatasetContractError("Payload SHA-256 does not match manifest")
    for name in ("atmospheric", "lightning"):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(providers[name]["checksum"])):
            raise DatasetContractError(f"providers.{name}.checksum must be a SHA-256 digest")
        try:
            cadence = float(providers[name]["cadence_minutes"])
            resolution = float(providers[name]["spatial_resolution_deg"])
        except (TypeError, ValueError) as exc:
            raise DatasetContractError(f"providers.{name} cadence/resolution must be numeric") from exc
        if cadence <= 0 or resolution <= 0:
            raise DatasetContractError(f"providers.{name} cadence/resolution must be positive")
        period = providers[name]["time_range"]
        if not isinstance(period, list) or len(period) != 2 or _parse_utc(period[0]) >= _parse_utc(period[1]):
            raise DatasetContractError(f"providers.{name}.time_range must be ordered [start, end]")
        geo = providers[name]["geographic_range"]
        try:
            if len(geo["lat"]) != 2 or len(geo["lon"]) != 2:
                raise ValueError
            if not (-90 <= float(geo["lat"][0]) < float(geo["lat"][1]) <= 90
                    and -180 <= float(geo["lon"][0]) < float(geo["lon"][1]) <= 180):
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetContractError(f"providers.{name}.geographic_range must contain valid lat/lon bounds") from exc

    try:
        with np.load(payload_path, allow_pickle=False) as archive:
            arrays = {key: archive[key].copy() for key in archive.files}
    except Exception as exc:
        raise DatasetContractError("Paired payload is not a valid safe NPZ file") from exc

    timestamp_sets: dict[str, tuple[datetime, datetime]] = {}
    seen_samples: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for split in SPLITS:
        keys = {f"X_{split}", f"y_{split}", f"target_observation_mask_{split}",
                f"timestamps_{split}", f"target_timestamps_{split}",
                f"availability_timestamps_{split}", f"valid_mask_{split}", "latitudes", "longitudes"}
        absent = keys - arrays.keys()
        if absent:
            raise DatasetContractError(f"Payload missing {split} arrays: {', '.join(sorted(absent))}")
        x, y = arrays[f"X_{split}"], arrays[f"y_{split}"]
        ts, target_ts = arrays[f"timestamps_{split}"], arrays[f"target_timestamps_{split}"]
        availability = arrays[f"availability_timestamps_{split}"]
        valid_mask = arrays[f"valid_mask_{split}"]
        target_observation_mask = arrays[f"target_observation_mask_{split}"]
        if x.ndim != 5 or y.ndim != 4:
            raise DatasetContractError(f"{split}: expected X=[N,T,C,H,W], y=[N,1,H,W]")
        n, t, c, h, w = x.shape
        if n < 1 or c != len(manifest["feature_order"]) or y.shape != (n, 1, h, w):
            raise DatasetContractError(f"{split}: X/y dimensions disagree with manifest or [N,1,H,W]")
        if (ts.shape != (n, t) or target_ts.shape != (n, 1)
                or availability.shape != (n, t, c) or valid_mask.shape != x.shape
                or valid_mask.dtype != np.bool_
                or target_observation_mask.shape != y.shape
                or target_observation_mask.dtype != np.bool_):
            raise DatasetContractError(f"{split}: timestamp dimensions do not match X/y")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise DatasetContractError(f"{split}: non-finite features or labels; missing data must be resolved before training")
        if np.any(np.abs(x[~valid_mask]) > 1e-6):
            raise DatasetContractError(f"{split}: invalid features must use the declared post-normalization mean fill of zero")
        if float((~valid_mask).mean()) > max_missing_fraction:
            raise DatasetContractError(f"{split}: missing-data fraction exceeds the declared quality threshold")
        if not np.isin(y, [0, 1]).all():
            raise DatasetContractError(f"{split}: lightning occurrence labels must be binary 0/1")
        observed_labels = y[target_observation_mask]
        if observed_labels.size == 0:
            raise DatasetContractError(f"{split}: no observed target labels; UNKNOWN-only samples cannot train or evaluate")
        if np.unique(observed_labels).size < 2:
            raise DatasetContractError(f"{split}: both event and non-event labels are required among observed targets")
        split_times = []
        previous_sample_start = None
        for i in range(n):
            inputs = [_parse_utc(str(v)) for v in ts[i]]
            targets = [_parse_utc(str(v)) for v in target_ts[i]]
            available_at = [[_parse_utc(str(v)) for v in row] for row in availability[i]]
            if len(set(inputs)) != len(inputs) or any(b <= a for a, b in zip(inputs, inputs[1:])):
                raise DatasetContractError(f"{split}: duplicate or non-monotonic input timestamps")
            if previous_sample_start is not None and inputs[0] <= previous_sample_start:
                raise DatasetContractError(f"{split}: samples are shuffled or duplicated instead of chronological")
            previous_sample_start = inputs[0]
            if targets[0] <= inputs[-1]:
                raise DatasetContractError(f"{split}: target time is not strictly after input time")
            if any(value > inputs[-1] for row in available_at for value in row):
                raise DatasetContractError(f"{split}: a feature was unavailable at forecast issue time")
            expected_step = cadence * 60
            if any((b - a).total_seconds() != expected_step for a, b in zip(inputs, inputs[1:])):
                raise DatasetContractError(f"{split}: input cadence differs from manifest")
            if (targets[0] - inputs[-1]).total_seconds() != expected_step * horizon:
                raise DatasetContractError(f"{split}: target time does not match configured forecast horizon")
            split_times.extend(inputs + targets)
            sample_id = (tuple(value.isoformat() for value in inputs), tuple(value.isoformat() for value in targets))
            if sample_id in seen_samples:
                raise DatasetContractError("Duplicate input/target sample occurs within or across splits")
            seen_samples.add(sample_id)
        timestamp_sets[split] = (min(split_times), max(split_times))
    lat, lon = arrays["latitudes"], arrays["longitudes"]
    if lat.ndim != 1 or lon.ndim != 1 or not np.isfinite(lat).all() or not np.isfinite(lon).all():
        raise DatasetContractError("Coordinates must be finite 1D latitude/longitude vectors")
    if np.any((lat < -90) | (lat > 90)) or np.any((lon < -180) | (lon > 180)):
        raise DatasetContractError("Coordinates fall outside WGS84 latitude/longitude bounds")
    if not np.all(np.diff(lat) > 0) or not np.all(np.diff(lon) > 0):
        raise DatasetContractError("Coordinate vectors must be strictly increasing")
    _, _, _, h, w = arrays["X_train"].shape
    if (len(lat), len(lon)) != (h, w):
        raise DatasetContractError("Coordinate vector lengths must match the model grid")
    grid = manifest["spatial_grid"]
    grid_fields = {"lat_min", "lat_max", "lon_min", "lon_max", "latitude_resolution_deg",
                   "longitude_resolution_deg", "n_lat", "n_lon"}
    if not isinstance(grid, dict) or grid_fields - grid.keys():
        raise DatasetContractError(f"spatial_grid missing fields: {', '.join(sorted(grid_fields - grid.keys())) if isinstance(grid, dict) else ', '.join(sorted(grid_fields))}")
    try:
        expected = (float(grid["lat_min"]), float(grid["lat_max"]), float(grid["lon_min"]),
                    float(grid["lon_max"]), float(grid["latitude_resolution_deg"]),
                    float(grid["longitude_resolution_deg"]))
        if (len(lat) != int(grid["n_lat"]) or len(lon) != int(grid["n_lon"])
                or not np.isclose(lat.min(), expected[0]) or not np.isclose(lat.max(), expected[1])
                or not np.isclose(lon.min(), expected[2]) or not np.isclose(lon.max(), expected[3])
                or (len(lat) > 1 and not np.allclose(np.diff(lat), expected[4], atol=1e-6))
                or (len(lon) > 1 and not np.allclose(np.diff(lon), expected[5], atol=1e-6))):
            raise ValueError
    except (TypeError, ValueError, KeyError) as exc:
        raise DatasetContractError("Coordinates do not match spatial_grid bounds, dimensions or resolution") from exc
    for name in ("atmospheric", "lightning"):
        period = providers[name]["time_range"]
        start, end = _parse_utc(period[0]), _parse_utc(period[1])
        if timestamp_sets["train"][0] < start or timestamp_sets["test"][1] > end:
            raise DatasetContractError(f"providers.{name}.time_range does not cover all model timestamps")
        geo = providers[name]["geographic_range"]
        if lat.min() < float(geo["lat"][0]) or lat.max() > float(geo["lat"][1]) or lon.min() < float(geo["lon"][0]) or lon.max() > float(geo["lon"][1]):
            raise DatasetContractError(f"providers.{name}.geographic_range does not cover the model grid")
    if not (timestamp_sets["train"][1] < timestamp_sets["validation"][0]
            and timestamp_sets["validation"][1] < timestamp_sets["test"][0]):
        raise DatasetContractError("Train, validation and test timestamps must be strictly ordered and non-overlapping")
    if timestamp_sets["train"][0] < collection_start or timestamp_sets["test"][1] > collection_end:
        raise DatasetContractError("collection_period does not cover all split input and target timestamps")
    fit_start, fit_end = (_parse_utc(v) for v in normalization["fit_time_range"])
    if not (timestamp_sets["train"][0] <= fit_start <= fit_end <= timestamp_sets["train"][1]):
        raise DatasetContractError("Normalization statistics use timestamps outside the training split")
    return RealDataset(arrays=arrays, manifest=manifest)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a provenance-bearing paired StrikeCast dataset.")
    parser.add_argument("--dataset", required=True, help="Directory containing manifest.json and the checksummed NPZ payload")
    args = parser.parse_args()
    validated = load_real_dataset(args.dataset)
    print(json.dumps({
        "status": "PASS",
        "dataset_version": validated.manifest["dataset_version"],
        "payload_sha256": validated.manifest["payload"]["sha256"],
        "feature_order": validated.manifest["feature_order"],
        "splits": {split: {"X": list(validated.arrays[f"X_{split}"].shape),
                           "y": list(validated.arrays[f"y_{split}"].shape)} for split in SPLITS},
    }, indent=2))
