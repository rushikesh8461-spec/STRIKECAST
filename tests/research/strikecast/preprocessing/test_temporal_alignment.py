import numpy as np
import pytest

from src.ingestion.contract import DataRecord, GridSpec, SourceType, VariableSpec
from src.preprocessing.temporal_alignment import (
    align_gridded_source,
    align_point_source_timestamps,
    build_common_grid,
    infer_temporal_resolution_minutes,
)


def _grid():
    lat = np.array([18.0, 18.5])
    lon = np.array([77.0, 77.5])
    return GridSpec(18.0, 18.5, 77.0, 77.5, 0.5, 0.5, 2, 2, lat, lon)


def _record(timestamps, data=None):
    grid = _grid()
    if data is None:
        data = np.random.default_rng(0).normal(size=(len(timestamps), 2, 2, 1)).astype(np.float32)
    return DataRecord(
        source=SourceType.SATELLITE,
        source_id="test",
        dataset_version="0.0.1",
        timestamps=timestamps,
        grid=grid,
        variables=[VariableSpec("x", "unit", "float32")],
        data=data,
    )


def test_infer_resolution_uses_configured_value_when_given():
    records = {"a": _record(["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"])}
    assert infer_temporal_resolution_minutes(records, configured=30) == 30.0


def test_infer_resolution_falls_back_to_finest_source():
    records = {
        "hourly": _record(["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z", "2026-06-01T02:00:00Z"]),
        "half_hourly": _record(["2026-06-01T00:00:00Z", "2026-06-01T00:30:00Z", "2026-06-01T01:00:00Z"]),
    }
    assert infer_temporal_resolution_minutes(records, configured=None) == 30.0


def test_infer_resolution_raises_when_no_signal_available():
    records = {"a": _record(["2026-06-01T00:00:00Z"])}  # single timestamp: no interval
    with pytest.raises(ValueError):
        infer_temporal_resolution_minutes(records, configured=None)


def test_common_grid_spans_intersection_not_union():
    records = {
        "a": _record(["2026-06-01T00:00:00Z", "2026-06-01T02:00:00Z"]),
        "b": _record(["2026-06-01T01:00:00Z", "2026-06-01T03:00:00Z"]),
    }
    grid = build_common_grid(records, resolution_minutes=60)
    # intersection of [00:00,02:00] and [01:00,03:00] is [01:00,02:00]
    assert grid[0] == "2026-06-01T01:00:00Z"
    assert grid[-1] == "2026-06-01T02:00:00Z"


def test_common_grid_raises_on_no_overlap():
    records = {
        "a": _record(["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"]),
        "b": _record(["2026-06-02T00:00:00Z", "2026-06-02T01:00:00Z"]),
    }
    with pytest.raises(ValueError):
        build_common_grid(records, resolution_minutes=60)


def test_align_gridded_source_matches_within_tolerance():
    data = np.arange(2 * 2 * 2 * 1, dtype=np.float32).reshape(2, 2, 2, 1)
    record = _record(["2026-06-01T00:02:00Z", "2026-06-01T01:02:00Z"], data=data)
    common_grid = ["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"]
    aligned = align_gridded_source(record, common_grid, tolerance_minutes=5)
    assert not np.isnan(aligned).any()
    np.testing.assert_array_equal(aligned, data)


def test_align_gridded_source_leaves_nan_outside_tolerance():
    data = np.ones((1, 2, 2, 1), dtype=np.float32)
    record = _record(["2026-06-01T00:20:00Z"], data=data)
    common_grid = ["2026-06-01T00:00:00Z"]
    aligned = align_gridded_source(record, common_grid, tolerance_minutes=5)
    assert np.isnan(aligned).all()


def test_align_point_source_assigns_to_next_causal_slot_and_drops_out_of_tolerance():
    points = [
        {"latitude": 18.1, "longitude": 77.1, "timestamp": "2026-06-01T00:03:00Z", "intensity": 1.0},
        {"latitude": 18.1, "longitude": 77.1, "timestamp": "2026-06-01T00:40:00Z", "intensity": 1.0},
    ]
    common_grid = ["2026-06-01T00:00:00Z", "2026-06-01T00:15:00Z"]
    aligned = align_point_source_timestamps(points, common_grid, tolerance_minutes=15)
    assert len(aligned) == 1
    assert aligned[0]["timestamp"] == "2026-06-01T00:15:00Z"
