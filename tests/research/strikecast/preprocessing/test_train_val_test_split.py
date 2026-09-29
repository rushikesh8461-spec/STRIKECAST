import pytest

from src.preprocessing.sequence import build_windows
from src.preprocessing.split import assign_windows_to_splits, compute_split_boundaries


def test_split_boundaries_respect_fractions():
    b = compute_split_boundaries(100, 0.6, 0.2, 0.2)
    assert b.train_end == 60
    assert b.val_end == 80
    assert b.n_timesteps == 100


def test_split_boundaries_rejects_bad_fractions():
    with pytest.raises(ValueError):
        compute_split_boundaries(100, 0.6, 0.2, 0.3)  # sums to 1.1


def test_windows_assigned_to_correct_chronological_split():
    windows = build_windows(n_timesteps=20, sequence_length=2, forecast_horizon=1, stride=1)
    boundaries = compute_split_boundaries(20, 0.6, 0.2, 0.2)  # train_end=12, val_end=16
    result = assign_windows_to_splits(windows, boundaries)

    for w in result["train"]:
        assert w.target_end <= boundaries.train_end
    for w in result["val"]:
        assert w.start >= boundaries.train_end and w.target_end <= boundaries.val_end
    for w in result["test"]:
        assert w.start >= boundaries.val_end and w.target_end <= boundaries.n_timesteps


def test_boundary_straddling_windows_are_dropped_not_duplicated():
    windows = build_windows(n_timesteps=20, sequence_length=2, forecast_horizon=1, stride=1)
    boundaries = compute_split_boundaries(20, 0.6, 0.2, 0.2)
    result = assign_windows_to_splits(windows, boundaries)

    total_assigned = len(result["train"]) + len(result["val"]) + len(result["test"])
    total_dropped = len(result["_dropped"])
    assert total_assigned + total_dropped == len(windows)

    # No window appears in more than one split.
    train_ids = {(w.start, w.target_end) for w in result["train"]}
    val_ids = {(w.start, w.target_end) for w in result["val"]}
    test_ids = {(w.start, w.target_end) for w in result["test"]}
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)


def test_short_segments_can_legitimately_yield_zero_windows():
    # 12 timesteps, window size 5 (L=4,H=1): val segment [7,10) has length 3 < 5.
    windows = build_windows(n_timesteps=12, sequence_length=4, forecast_horizon=1, stride=1)
    boundaries = compute_split_boundaries(12, 0.6, 0.2, 0.2)
    result = assign_windows_to_splits(windows, boundaries)
    assert len(result["val"]) == 0
    assert len(result["test"]) == 0
    assert len(result["train"]) > 0
