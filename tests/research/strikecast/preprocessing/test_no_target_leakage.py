"""
Proves 'targets must never leak into input features' at the WindowDataset
level: X for a window is built purely from feature_tensor[start:input_end]
and y purely from target_grid[input_end:target_end] — disjoint, ordered
index ranges — by embedding the time index itself into the arrays and
checking the recovered values.
"""

import numpy as np

from src.preprocessing.dataset import WindowDataset
from src.preprocessing.sequence import build_windows


def _time_stamped_arrays(n_t=12, n_lat=2, n_lon=2, n_channels=1):
    # feature_tensor[t] == t everywhere (broadcast), so recovering the value
    # tells us exactly which time index a slice actually came from.
    feature_tensor = np.zeros((n_t, n_lat, n_lon, n_channels), dtype=np.float32)
    for t in range(n_t):
        feature_tensor[t] = t
    valid_mask = np.ones_like(feature_tensor, dtype=bool)
    target_grid = np.zeros((n_t, n_lat, n_lon), dtype=np.float32)
    for t in range(n_t):
        target_grid[t] = t
    return feature_tensor, valid_mask, target_grid


def test_window_dataset_X_never_contains_a_target_time_index():
    feature_tensor, valid_mask, target_grid = _time_stamped_arrays()
    windows = build_windows(n_timesteps=12, sequence_length=4, forecast_horizon=2, stride=1)
    ds = WindowDataset(
        feature_tensor, valid_mask, target_grid, windows,
        channel_names=["dummy"], target_mode="strike_count", feature_schema=[],
    )
    for i in range(len(ds)):
        sample = ds[i]
        w = sample["window"]
        x_time_values = set(np.unique(sample["X"]).tolist())
        y_time_values = set(np.unique(sample["y"]).tolist())
        assert x_time_values == set(w.input_indices)
        assert y_time_values == set(w.target_indices)
        # No overlap between what X actually contains and what y actually contains.
        assert x_time_values.isdisjoint(y_time_values)


def test_window_dataset_y_never_contains_an_input_time_index():
    feature_tensor, valid_mask, target_grid = _time_stamped_arrays()
    windows = build_windows(n_timesteps=12, sequence_length=3, forecast_horizon=1, stride=1)
    ds = WindowDataset(
        feature_tensor, valid_mask, target_grid, windows,
        channel_names=["dummy"], target_mode="strike_count", feature_schema=[],
    )
    for i in range(len(ds)):
        sample = ds[i]
        w = sample["window"]
        y_time_values = set(np.unique(sample["y"]).tolist())
        assert y_time_values == set(w.target_indices)
        assert all(t >= w.input_end for t in y_time_values)
