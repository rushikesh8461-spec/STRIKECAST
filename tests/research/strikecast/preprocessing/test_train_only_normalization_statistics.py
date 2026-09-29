"""
Regression test for the Phase 7 critical rule at the build_dataset()
integration level (not just the fit_normalization_stats() unit level):
extreme values planted ONLY in the val/test time range must not shift the
fitted mean/std at all, proving build_dataset() really does slice
TRAIN-only data before calling fit_normalization_stats().
"""

from __future__ import annotations

import numpy as np
import pytest

from src.ingestion.contract import DataRecord, GridSpec, QualityReport, QualityStatus, SchemaStatus, SourceType, VariableSpec
from src.preprocessing import dataset as dataset_module
from src.preprocessing.config import load_config


N_T = 20  # long enough for non-empty train/val/test at default sequence settings


def _timestamps(n=N_T):
    return [f"2026-06-01T{h:02d}:00:00Z" for h in range(n)]


def _grid():
    lat = np.array([18.0, 18.5, 19.0])
    lon = np.array([77.0, 77.5, 78.0])
    return GridSpec(18.0, 19.0, 77.0, 78.0, 0.5, 0.5, 3, 3, lat, lon)


def _ok_quality():
    return QualityReport(
        source=SourceType.SATELLITE, generated_at="2026-01-01T00:00:00Z",
        timestamp_range=("", ""), coverage_fraction=1.0, missing_fraction=0.0,
        valid_fraction=1.0, schema_status=SchemaStatus.VALID, quality_status=QualityStatus.OK,
    )


def _gridded_record(source_type, source_id, variables, base_value, poison_val_test=False):
    grid = _grid()
    n_t, n_lat, n_lon, n_var = N_T, grid.n_lat, grid.n_lon, len(variables)
    data = np.full((n_t, n_lat, n_lon, n_var), float(base_value), dtype=np.float32)
    if poison_val_test:
        # Plant an extreme value ONLY in the timestamps that fall in the
        # val/test time range (index >= train_end for default 0.6 split).
        train_end = round(0.6 * n_t)
        data[train_end:] = 1e6
    return DataRecord(
        source=source_type, source_id=source_id, dataset_version="0.0.1",
        timestamps=_timestamps(n_t), grid=grid, variables=variables, data=data,
        quality=_ok_quality(),
    )


@pytest.fixture
def poisoned_records():
    sat_vars = [VariableSpec("brightness_temperature", "K", "float32"), VariableSpec("cloud_top_height_estimate", "km", "float32")]
    nwp_vars = [
        VariableSpec("temperature_2m", "K", "float32"), VariableSpec("relative_humidity", "%", "float32"),
        VariableSpec("surface_pressure", "hPa", "float32"), VariableSpec("wind_u", "m/s", "float32"),
        VariableSpec("wind_v", "m/s", "float32"), VariableSpec("cape", "J/kg", "float32"),
        VariableSpec("cin", "J/kg", "float32"),
    ]
    radar_vars = [VariableSpec("reflectivity", "dBZ", "float32")]

    return {
        "satellite": _gridded_record(SourceType.SATELLITE, "sat", sat_vars, base_value=290.0, poison_val_test=True),
        "nwp": _gridded_record(SourceType.NWP, "nwp", nwp_vars, base_value=10.0),
        "radar": _gridded_record(SourceType.RADAR, "radar", radar_vars, base_value=5.0),
        "lightning": DataRecord(
            source=SourceType.LIGHTNING, source_id="lightning", dataset_version="0.0.1",
            timestamps=_timestamps(N_T), grid=None,
            variables=[VariableSpec("intensity", "kA", "float32")],
            data=None, point_data=[], quality=_ok_quality(),
        ),
    }


def test_val_test_extreme_values_never_shift_normalization_stats(poisoned_records, monkeypatch):
    monkeypatch.setattr(
        dataset_module, "load_all_records", lambda config, demo=True: poisoned_records
    )
    config = load_config()
    bundle = dataset_module.build_dataset(config, demo=True)

    bt_stats = bundle.normalization_stats["brightness_temperature"]
    # The poisoned (1e6) values only ever appear at time indices >= train_end
    # (val/test range). If they leaked into the fit, the mean would be
    # enormous (>> 290). Confirm it is exactly the unpoisoned train-region
    # value's statistics instead.
    assert abs(bt_stats["mean"] - 290.0) < 1e-3
    assert bt_stats["std"] == config.normalization_cfg()["std_floor"]  # constant in train region -> floor
