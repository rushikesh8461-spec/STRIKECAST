import numpy as np
import pytest

from src.preprocessing.target import (
    ObservationState,
    build_observation_aware_target,
    build_target_grid,
)


def test_occurrence_mode_thresholds_correctly():
    counts = np.array([[[0, 1], [2, 0]]], dtype=np.float32)  # [time=1, lat=2, lon=2]
    y = build_target_grid(counts, mode="occurrence", occurrence_threshold=1)
    np.testing.assert_array_equal(y, np.array([[[0, 1], [1, 0]]], dtype=np.float32))


def test_occurrence_mode_higher_threshold():
    counts = np.array([[[0, 1], [2, 3]]], dtype=np.float32)
    y = build_target_grid(counts, mode="occurrence", occurrence_threshold=2)
    np.testing.assert_array_equal(y, np.array([[[0, 0], [1, 1]]], dtype=np.float32))


def test_strike_count_mode_passes_through():
    counts = np.array([[[0, 1], [2, 3]]], dtype=np.float32)
    y = build_target_grid(counts, mode="strike_count", occurrence_threshold=1)
    np.testing.assert_array_equal(y, counts)


def test_unknown_mode_raises():
    counts = np.zeros((1, 2, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        build_target_grid(counts, mode="not_a_mode", occurrence_threshold=1)


def test_unobserved_cells_remain_unknown_not_negative():
    counts = np.array([[[0.0, 2.0], [np.nan, 0.0]]], dtype=np.float32)
    observed = np.array([[[True, True], [True, False]]])
    result = build_observation_aware_target(counts, observed, occurrence_threshold=1)
    np.testing.assert_array_equal(result.observation_mask, [[[True, True], [False, False]]])
    np.testing.assert_array_equal(result.states, [[[ObservationState.NEGATIVE, ObservationState.POSITIVE],
                                                    [ObservationState.UNKNOWN, ObservationState.UNKNOWN]]])
    np.testing.assert_array_equal(result.values, [[[0.0, 1.0], [0.0, 0.0]]])


def test_quality_mask_can_only_remove_labels():
    counts = np.array([[[0.0, 3.0]]], dtype=np.float32)
    result = build_observation_aware_target(counts, np.ones_like(counts, dtype=bool),
                                           quality_mask=np.array([[[False, True]]], dtype=bool))
    np.testing.assert_array_equal(result.states, [[[ObservationState.UNKNOWN, ObservationState.POSITIVE]]])
