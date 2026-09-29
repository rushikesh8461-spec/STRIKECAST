"""
Proves 'INPUT TIME < TARGET TIME' (spec Phase 10) holds for every window
build_windows() can ever produce, across a wide range of configurations —
not just the default one. This is a property test on the arithmetic in
sequence.py, since that module is the single place deciding which indices
are input vs target (see its module docstring).
"""

import pytest

from src.preprocessing.sequence import build_windows


@pytest.mark.parametrize("n_timesteps", [5, 12, 20, 60])
@pytest.mark.parametrize("sequence_length", [1, 2, 4, 6])
@pytest.mark.parametrize("forecast_horizon", [1, 2, 3])
@pytest.mark.parametrize("stride", [1, 2])
def test_every_target_index_strictly_after_every_input_index(
    n_timesteps, sequence_length, forecast_horizon, stride
):
    windows = build_windows(n_timesteps, sequence_length, forecast_horizon, stride)
    for w in windows:
        input_max = max(w.input_indices)
        target_min = min(w.target_indices)
        assert target_min > input_max, (
            f"Leakage: window {w} has a target index <= an input index."
        )


def test_windows_never_read_past_available_timeline():
    windows = build_windows(n_timesteps=12, sequence_length=4, forecast_horizon=2, stride=1)
    for w in windows:
        assert w.target_end <= 12
