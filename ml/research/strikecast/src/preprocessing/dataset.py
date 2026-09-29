"""
Phase 12 — Dataset object / loader. The single public entry point M3
should use:

    from src.preprocessing.dataset import build_dataset
    from src.preprocessing.config import load_config

    bundle = build_dataset(load_config())
    train_ds = bundle.splits["train"]
    sample = train_ds[0]
    X, y, mask = sample["X"], sample["y"], sample["mask"]

M3 does not need to know about M1's DataRecord, alignment, gridding,
normalization statistics, or window bookkeeping to use this — see
docs/m2_m3_contract.md for the full input/output schema this produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.features.schema import get_feature_schema
from src.ingestion.contract import DataRecord

from .config import PreprocessingConfig
from .feature_pipeline import build_feature_tensor
from .loading import load_all_records
from .missing_data import apply_validity_mask_fill
from .normalization import apply_normalization, fit_normalization_stats
from .spatial_alignment import bin_lightning_to_grid, determine_target_grid, regrid_nearest
from .split import SplitBoundaries, assign_windows_to_splits, compute_split_boundaries
from .sequence import Window, build_windows
from .target import build_target_grid
from .temporal_alignment import (
    align_gridded_source,
    align_point_source_timestamps,
    build_common_grid,
    infer_temporal_resolution_minutes,
)

_GRIDDED_SOURCES = ("satellite", "nwp", "radar")


class WindowDataset:
    """A single split's windows, ready for M3 to index into directly.
    Framework-agnostic (plain Python + numpy) so it imposes no PyTorch/
    TensorFlow dependency on this module — wrapping it in a
    torch.utils.data.Dataset is a one-line adapter left to M3:

        class TorchWrap(torch.utils.data.Dataset):
            def __init__(self, wd): self.wd = wd
            def __len__(self): return len(self.wd)
            def __getitem__(self, i):
                s = self.wd[i]
                return torch.from_numpy(s["X"]), torch.from_numpy(s["y"])
    """

    def __init__(
        self,
        feature_tensor: np.ndarray,
        valid_mask: np.ndarray,
        target_grid: np.ndarray,
        windows: list[Window],
        channel_names: list[str],
        target_mode: str,
        feature_schema: list[dict],
    ):
        self.feature_tensor = feature_tensor  # [T, lat, lon, C], normalized + filled
        self.valid_mask = valid_mask          # [T, lat, lon, C], bool
        self.target_grid = target_grid        # [T, lat, lon]
        self.windows = windows
        self.channel_names = channel_names
        self.target_mode = target_mode
        self.feature_schema = feature_schema

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, i: int) -> dict:
        w = self.windows[i]
        X = self.feature_tensor[w.start : w.input_end]        # [L, lat, lon, C]
        mask = self.valid_mask[w.start : w.input_end]           # [L, lat, lon, C]
        y = self.target_grid[w.input_end : w.target_end]        # [H, lat, lon]
        return {"X": X, "mask": mask, "y": y, "window": w}

    def get_feature_schema(self) -> list[dict]:
        return self.feature_schema

    def get_target_schema(self) -> dict:
        return {
            "name": "lightning_occurrence" if self.target_mode == "occurrence" else "lightning_strike_count",
            "mode": self.target_mode,
            "dimensions": "[forecast_horizon, lat, lon]",
        }


@dataclass
class DatasetBundle:
    splits: dict[str, WindowDataset]
    channel_names: list[str]
    normalization_stats: dict
    metadata: dict = field(default_factory=dict)


def _extract_source_channels(record: DataRecord) -> dict[str, np.ndarray]:
    """Split a gridded DataRecord's [time, lat, lon, var] array into
    {variable_name: [time, lat, lon]} using record.variables order —
    never assumes a fixed index, always reads the schema M1 attached."""
    return {
        var.name: record.data[..., i] for i, var in enumerate(record.variables)
    }


def build_dataset(
    config: PreprocessingConfig, demo: bool = True
) -> DatasetBundle:
    if not demo:
        raise RuntimeError(
            "The legacy M1/M2 raw-record path does not yet carry a full-target-interval "
            "LIS observation mask. It is blocked for real training; prepare a "
            "provenance-complete paired dataset through the observation-aware target contract."
        )
    warnings: list[str] = []

    # --- Phase 2/3: read M1's validated output ---
    records = load_all_records(config, demo=demo)
    gridded_records = {k: v for k, v in records.items() if k in _GRIDDED_SOURCES}
    lightning_record = records["lightning"]

    # --- Phase 4: temporal alignment ---
    temporal_cfg = config.temporal_alignment_cfg()
    resolution = infer_temporal_resolution_minutes(
        records, temporal_cfg.get("target_resolution_minutes")
    )
    common_grid = build_common_grid(records, resolution)
    tolerance = temporal_cfg["nearest_neighbor_tolerance_minutes"]

    # --- Phase 5: spatial alignment ---
    spatial_cfg = config.spatial_alignment_cfg()
    target_grid = determine_target_grid(gridded_records, spatial_cfg)

    channel_arrays: dict[str, np.ndarray] = {}
    source_dataset_versions: dict[str, str] = {}
    for name, record in gridded_records.items():
        aligned = align_gridded_source(record, common_grid, tolerance)
        regridded = regrid_nearest(aligned, record.grid.lat_values, record.grid.lon_values, target_grid)
        per_var = {
            var.name: regridded[..., i] for i, var in enumerate(record.variables)
        }
        channel_arrays.update(per_var)
        source_dataset_versions[name] = record.dataset_version

    aligned_points = align_point_source_timestamps(
        lightning_record.point_data or [], common_grid, tolerance
    )
    n_points_before = len(lightning_record.point_data or [])
    n_points_after = len(aligned_points)
    if n_points_after < n_points_before:
        warnings.append(
            f"{n_points_before - n_points_after} lightning strike(s) dropped: "
            f"no common-grid timestamp within {tolerance} min tolerance."
        )
    strike_count, mean_abs_intensity = bin_lightning_to_grid(aligned_points, common_grid, target_grid)
    channel_arrays["lightning_strike_count"] = strike_count
    channel_arrays["lightning_mean_abs_intensity"] = mean_abs_intensity
    source_dataset_versions["lightning"] = lightning_record.dataset_version

    # --- Missing-data masking + causal feature engineering ---
    features_cfg = config.features_cfg()
    missing_cfg = config.missing_data_cfg()
    feature_tensor_nan, valid_mask, channel_names = build_feature_tensor(
        channel_arrays,
        enabled_derived=features_cfg["enabled_derived_features"],
        lightning_recent_count_window_steps=features_cfg["lightning_recent_count_window_steps"],
    )

    feature_schema = get_feature_schema(features_cfg["enabled_derived_features"])

    # --- Phase 10: target construction ---
    target_cfg = config.target_cfg()
    target_grid_full = build_target_grid(
        strike_count, target_cfg["mode"], target_cfg["occurrence_threshold_strikes"]
    )

    # --- Phase 9: sequence/window construction ---
    seq_cfg = config.sequence_cfg()
    windows = build_windows(
        n_timesteps=len(common_grid),
        sequence_length=seq_cfg["sequence_length"],
        forecast_horizon=seq_cfg["forecast_horizon"],
        stride=seq_cfg["stride"],
    )

    # --- Phase 11: leakage-safe chronological split ---
    split_cfg = config.split_cfg()
    boundaries = compute_split_boundaries(
        len(common_grid), split_cfg["train_fraction"], split_cfg["val_fraction"], split_cfg["test_fraction"]
    )
    split_windows = assign_windows_to_splits(windows, boundaries)
    if split_windows["_dropped"]:
        warnings.append(
            f"{len(split_windows['_dropped'])} window(s) dropped: their "
            "input+target range straddled a train/val/test boundary."
        )

    # --- Phase 7: normalization (TRAIN split input-time range only) ---
    norm_cfg = config.normalization_cfg()
    train_tensor = feature_tensor_nan[0 : boundaries.train_end]
    train_valid = valid_mask[0 : boundaries.train_end]
    stats = fit_normalization_stats(
        train_tensor, train_valid, channel_names, norm_cfg["std_floor"]
    )
    normalized = apply_normalization(feature_tensor_nan, channel_names, stats)
    final_tensor = apply_validity_mask_fill(
        normalized, valid_mask, missing_cfg["fill_value_after_normalization"]
    )

    # --- Phase 6 (window-level): drop windows still too incomplete ---
    max_missing_frac = missing_cfg["max_missing_fraction_per_window"]
    final_split_windows: dict[str, list[Window]] = {}
    for split_name in ("train", "val", "test"):
        kept = []
        n_dropped_missing = 0
        for w in split_windows[split_name]:
            window_mask = valid_mask[w.start : w.input_end]
            missing_frac = 1.0 - float(np.mean(window_mask))
            if missing_frac <= max_missing_frac:
                kept.append(w)
            else:
                n_dropped_missing += 1
        if n_dropped_missing:
            warnings.append(
                f"{split_name}: {n_dropped_missing} window(s) dropped for exceeding "
                f"max_missing_fraction_per_window={max_missing_frac}."
            )
        final_split_windows[split_name] = kept
        if not kept:
            warnings.append(
                f"{split_name}: 0 windows available at the current sequence_length="
                f"{seq_cfg['sequence_length']}/forecast_horizon={seq_cfg['forecast_horizon']}/"
                f"split fractions on a {len(common_grid)}-timestep timeline. "
                "See docs/m2_m3_contract.md 'Known limitations'."
            )

    splits = {
        name: WindowDataset(
            feature_tensor=final_tensor,
            valid_mask=valid_mask,
            target_grid=target_grid_full,
            windows=ws,
            channel_names=channel_names,
            target_mode=target_cfg["mode"],
            feature_schema=feature_schema,
        )
        for name, ws in final_split_windows.items()
    }

    metadata = {
        "preprocessing_version": config.reproducibility_cfg()["preprocessing_version"],
        "split_version": "chronological-whole-window-v1",
        "source_dataset_versions": source_dataset_versions,
        "common_grid": {"n_timesteps": len(common_grid), "start": common_grid[0], "end": common_grid[-1]},
        "target_grid": {
            "n_lat": target_grid.n_lat,
            "n_lon": target_grid.n_lon,
            "lat_resolution_deg": target_grid.lat_resolution_deg,
            "lon_resolution_deg": target_grid.lon_resolution_deg,
        },
        "channel_names": channel_names,
        "sequence_length": seq_cfg["sequence_length"],
        "forecast_horizon": seq_cfg["forecast_horizon"],
        "stride": seq_cfg["stride"],
        "split_boundaries": {"train_end": boundaries.train_end, "val_end": boundaries.val_end, "n_timesteps": boundaries.n_timesteps},
        "split_time_ranges": {
            name: ({
                "first_input_time": common_grid[ws[0].start],
                "last_input_time": common_grid[ws[-1].input_end - 1],
                "first_target_time": common_grid[ws[0].input_end],
                "last_target_time": common_grid[ws[-1].target_end - 1],
                "window_count": len(ws),
            } if ws else {"first_input_time": None, "last_input_time": None,
                         "first_target_time": None, "last_target_time": None, "window_count": 0})
            for name, ws in final_split_windows.items()
        },
        "n_windows": {k: len(v) for k, v in final_split_windows.items()},
        "warnings": warnings,
    }

    return DatasetBundle(
        splits=splits,
        channel_names=channel_names,
        normalization_stats=stats,
        metadata=metadata,
    )
