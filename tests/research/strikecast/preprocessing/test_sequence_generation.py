import pytest

from src.preprocessing.sequence import Window, build_windows


def test_window_index_ranges():
    w = Window(start=2, input_end=5, target_end=7)
    assert list(w.input_indices) == [2, 3, 4]
    assert list(w.target_indices) == [5, 6]
    assert list(w.full_indices) == [2, 3, 4, 5, 6]


def test_build_windows_count_and_stride():
    # T=10, L=3, H=1 -> window_size=4 -> starts 0..6 inclusive (7 windows) at stride 1
    windows = build_windows(n_timesteps=10, sequence_length=3, forecast_horizon=1, stride=1)
    assert len(windows) == 7
    assert windows[0].start == 0 and windows[0].input_end == 3 and windows[0].target_end == 4
    assert windows[-1].start == 6 and windows[-1].target_end == 10


def test_build_windows_respects_stride():
    windows = build_windows(n_timesteps=10, sequence_length=3, forecast_horizon=1, stride=2)
    starts = [w.start for w in windows]
    assert starts == [0, 2, 4, 6]


def test_build_windows_empty_when_too_short():
    windows = build_windows(n_timesteps=3, sequence_length=3, forecast_horizon=1, stride=1)
    assert windows == []


@pytest.mark.parametrize("bad_kwargs", [
    dict(sequence_length=0, forecast_horizon=1, stride=1),
    dict(sequence_length=1, forecast_horizon=0, stride=1),
    dict(sequence_length=1, forecast_horizon=1, stride=0),
])
def test_build_windows_rejects_invalid_params(bad_kwargs):
    with pytest.raises(ValueError):
        build_windows(n_timesteps=10, **bad_kwargs)
