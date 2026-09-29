import numpy as np

from src.preprocessing.spatial_alignment import (
    TargetGrid,
    bin_lightning_to_grid,
    regrid_nearest,
)


def _target():
    return TargetGrid(
        lat_values=np.array([18.0, 18.5, 19.0]),
        lon_values=np.array([77.0, 77.5, 78.0]),
        lat_resolution_deg=0.5,
        lon_resolution_deg=0.5,
    )


def test_regrid_identity_fast_path_when_grids_match():
    target = _target()
    data = np.arange(1 * 3 * 3 * 1, dtype=np.float32).reshape(1, 3, 3, 1)
    out = regrid_nearest(data, target.lat_values, target.lon_values, target)
    np.testing.assert_array_equal(out, data)


def test_regrid_nearest_neighbor_mismatched_grid():
    target = _target()
    # source grid offset by a small amount, same resolution/extent
    src_lat = np.array([18.05, 18.55, 19.05])
    src_lon = np.array([77.05, 77.55, 78.05])
    data = np.arange(1 * 3 * 3 * 1, dtype=np.float32).reshape(1, 3, 3, 1)
    out = regrid_nearest(data, src_lat, src_lon, target)
    assert out.shape == (1, 3, 3, 1)
    # each target cell's nearest source cell is the same index here (small offset)
    np.testing.assert_array_equal(out, data)


def test_bin_lightning_to_grid_counts_and_intensity():
    target = _target()
    common_grid = ["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"]
    points = [
        {"latitude": 18.0, "longitude": 77.0, "timestamp": "2026-06-01T00:00:00Z", "intensity": 10.0},
        {"latitude": 18.0, "longitude": 77.0, "timestamp": "2026-06-01T00:00:00Z", "intensity": -20.0},
        {"latitude": 19.0, "longitude": 78.0, "timestamp": "2026-06-01T01:00:00Z", "intensity": 5.0},
    ]
    count, mean_abs_intensity = bin_lightning_to_grid(points, common_grid, target)
    assert count.shape == (2, 3, 3)
    assert count[0, 0, 0] == 2
    assert count[1, 2, 2] == 1
    assert mean_abs_intensity[0, 0, 0] == 15.0  # mean(|10|, |-20|)
    assert mean_abs_intensity[1, 2, 2] == 5.0
    assert count.sum() == 3


def test_bin_lightning_to_grid_empty_points():
    target = _target()
    common_grid = ["2026-06-01T00:00:00Z"]
    count, mean_abs_intensity = bin_lightning_to_grid([], common_grid, target)
    assert count.shape == (1, 3, 3)
    assert count.sum() == 0
    assert mean_abs_intensity.sum() == 0


def test_bin_lightning_to_grid_drops_points_with_unmatched_timestamp():
    target = _target()
    common_grid = ["2026-06-01T00:00:00Z"]
    points = [
        {"latitude": 18.0, "longitude": 77.0, "timestamp": "2026-06-01T05:00:00Z", "intensity": 1.0},
    ]
    count, _ = bin_lightning_to_grid(points, common_grid, target)
    assert count.sum() == 0
