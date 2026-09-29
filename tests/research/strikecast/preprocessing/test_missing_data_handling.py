import numpy as np

from src.preprocessing.missing_data import apply_validity_mask_fill, interpolate_temporal_gaps


def test_interior_gap_remains_missing_instead_of_using_a_future_observation():
    data = np.array([[[[1.0]]], [[[np.nan]]], [[[3.0]]]], dtype=np.float32)
    preserved, valid = interpolate_temporal_gaps(data, max_gap_steps=2)
    assert np.isnan(preserved[1, 0, 0, 0])
    assert not valid[1, 0, 0, 0]


def test_long_interior_gap_remains_missing():
    data = np.array([[[[1.0]]], [[[np.nan]]], [[[np.nan]]], [[[np.nan]]], [[[5.0]]]], dtype=np.float32)
    preserved, valid = interpolate_temporal_gaps(data, max_gap_steps=2)
    assert np.isnan(preserved[1:4, 0, 0, 0]).all()
    assert not valid[1:4, 0, 0, 0].any()


def test_future_observation_cannot_change_prior_missing_input():
    before = np.array([[[[1.0]]], [[[np.nan]]], [[[3.0]]]], dtype=np.float32)
    changed_future = before.copy()
    changed_future[2, 0, 0, 0] = 900.0
    left, _ = interpolate_temporal_gaps(before, max_gap_steps=2)
    right, _ = interpolate_temporal_gaps(changed_future, max_gap_steps=2)
    assert np.isnan(left[1, 0, 0, 0]) and np.isnan(right[1, 0, 0, 0])


def test_leading_and_trailing_missing_values_are_preserved():
    data = np.array([[[[np.nan]]], [[[2.0]]], [[[3.0]]], [[[np.nan]]]], dtype=np.float32)
    preserved, valid = interpolate_temporal_gaps(data, max_gap_steps=5)
    assert np.isnan(preserved[[0, 3], 0, 0, 0]).all()
    assert not valid[[0, 3], 0, 0, 0].any()


def test_fully_missing_series_untouched():
    data = np.full((4, 1, 1, 1), np.nan, dtype=np.float32)
    preserved, valid = interpolate_temporal_gaps(data, max_gap_steps=2)
    assert np.isnan(preserved).all()
    assert not valid.any()


def test_apply_validity_mask_fill_replaces_only_invalid():
    data = np.array([1.0, np.nan, 3.0], dtype=np.float32)
    mask = np.array([True, False, True])
    out = apply_validity_mask_fill(data, mask, fill_value=0.0)
    np.testing.assert_array_equal(out, np.array([1.0, 0.0, 3.0], dtype=np.float32))
