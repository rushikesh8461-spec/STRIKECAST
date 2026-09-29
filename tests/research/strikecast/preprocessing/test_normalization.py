import numpy as np

from src.preprocessing.normalization import apply_normalization, fit_normalization_stats


def test_fit_normalization_stats_basic_mean_std():
    # single channel, all valid, values 1..4 -> mean=2.5, std=sqrt(1.25)
    tensor = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32).reshape(4, 1, 1, 1)
    valid = np.ones_like(tensor, dtype=bool)
    stats = fit_normalization_stats(tensor, valid, ["x"], std_floor=1e-6)
    assert abs(stats["x"]["mean"] - 2.5) < 1e-5
    assert abs(stats["x"]["std"] - np.std([1, 2, 3, 4])) < 1e-5


def test_fit_normalization_stats_ignores_invalid_values():
    tensor = np.array([1.0, 999.0, 3.0], dtype=np.float32).reshape(3, 1, 1, 1)
    valid = np.array([True, False, True]).reshape(3, 1, 1, 1)
    stats = fit_normalization_stats(tensor, valid, ["x"], std_floor=1e-6)
    # 999 (invalid) must not influence the mean
    assert abs(stats["x"]["mean"] - 2.0) < 1e-5


def test_std_floor_applied_for_constant_channel():
    tensor = np.full((5, 1, 1, 1), 7.0, dtype=np.float32)
    valid = np.ones_like(tensor, dtype=bool)
    stats = fit_normalization_stats(tensor, valid, ["x"], std_floor=1e-3)
    assert stats["x"]["std"] == 1e-3


def test_no_valid_values_falls_back_to_identity_stats():
    tensor = np.full((3, 1, 1, 1), np.nan, dtype=np.float32)
    valid = np.zeros_like(tensor, dtype=bool)
    stats = fit_normalization_stats(tensor, valid, ["x"], std_floor=1e-6)
    assert stats["x"] == {"mean": 0.0, "std": 1.0}


def test_apply_normalization_zscores_correctly():
    tensor = np.array([2.0, 4.0], dtype=np.float32).reshape(2, 1, 1, 1)
    stats = {"x": {"mean": 3.0, "std": 1.0}}
    out = apply_normalization(tensor, ["x"], stats)
    np.testing.assert_allclose(out.flatten(), [-1.0, 1.0])
