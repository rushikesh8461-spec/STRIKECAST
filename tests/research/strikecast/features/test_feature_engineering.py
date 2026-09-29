import numpy as np

from src.features.engineering import (
    causal_rolling_sum,
    compute_derived_features,
    spatial_gradient_magnitude,
    temporal_diff,
    wind_speed,
)


def test_wind_speed_pythagorean():
    u = np.array([[[3.0]]])
    v = np.array([[[4.0]]])
    out = wind_speed(u, v)
    np.testing.assert_allclose(out, [[[5.0]]])


def test_temporal_diff_first_step_is_zero():
    channel = np.array([[[10.0]], [[15.0]], [[12.0]]])  # [time=3,1,1]
    out = temporal_diff(channel)
    assert out[0, 0, 0] == 0.0
    assert out[1, 0, 0] == 5.0
    assert out[2, 0, 0] == -3.0


def test_temporal_diff_never_uses_future_step():
    # Changing channel[2] must not affect out[0] or out[1] (causality).
    channel_a = np.array([[[1.0]], [[2.0]], [[100.0]]])
    channel_b = np.array([[[1.0]], [[2.0]], [[-999.0]]])
    out_a = temporal_diff(channel_a)
    out_b = temporal_diff(channel_b)
    np.testing.assert_array_equal(out_a[:2], out_b[:2])


def test_causal_rolling_sum_matches_manual_window():
    channel = np.array([[[1.0]], [[2.0]], [[3.0]], [[4.0]]])  # t=0..3
    out = causal_rolling_sum(channel, window_steps=2)
    # t=0: just [1] -> 1 ; t=1: [1,2] -> 3 ; t=2: [2,3] -> 5 ; t=3: [3,4] -> 7
    np.testing.assert_allclose(out.flatten(), [1.0, 3.0, 5.0, 7.0])


def test_causal_rolling_sum_never_uses_future_step():
    channel_a = np.array([[[1.0]], [[2.0]], [[999.0]]])
    channel_b = np.array([[[1.0]], [[2.0]], [[-999.0]]])
    out_a = causal_rolling_sum(channel_a, window_steps=2)
    out_b = causal_rolling_sum(channel_b, window_steps=2)
    np.testing.assert_array_equal(out_a[:2], out_b[:2])


def test_spatial_gradient_magnitude_zero_for_uniform_field():
    channel = np.full((1, 4, 4), 42.0)
    out = spatial_gradient_magnitude(channel)
    np.testing.assert_allclose(out, 0.0)


def test_spatial_gradient_magnitude_nonzero_at_edge():
    channel = np.zeros((1, 4, 4))
    channel[0, :, 2:] = 10.0  # a sharp edge halfway across
    out = spatial_gradient_magnitude(channel)
    assert out[0, 0, 1] > 0
    assert out[0, 0, 0] >= 0


def test_compute_derived_features_respects_enabled_list():
    base = {
        "wind_u": np.zeros((2, 2, 2)), "wind_v": np.zeros((2, 2, 2)),
        "cape": np.zeros((2, 2, 2)), "cin": np.zeros((2, 2, 2)),
        "reflectivity": np.zeros((2, 2, 2)), "brightness_temperature": np.zeros((2, 2, 2)),
        "lightning_strike_count": np.zeros((2, 2, 2)),
    }
    out = compute_derived_features(base, enabled=["wind_speed"], lightning_recent_count_window_steps=3)
    assert set(out.keys()) == {"wind_speed"}
