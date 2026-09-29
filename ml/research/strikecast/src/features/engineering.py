"""
Phase 8 — Feature engineering.

Computes each enabled derived feature from the base (aligned, cleaned)
tensor. Every function here is CAUSAL: computing the value at time t uses
only base data at times <= t (from the same aligned tensor position), and
the first step of any temporal-difference/rolling feature is defined as 0
(no prior step exists) rather than reaching outside the array or wrapping
around. This matters because derived features become part of X — the
model input — at every input timestep, so they must never encode
information from a future timestep.

See src/features/schema.py for the FEATURE/SOURCE/FORMULA/UNITS/
DIMENSIONS/WHY documentation table this module implements.
"""

from __future__ import annotations

import numpy as np


def _causal_diff(channel: np.ndarray) -> np.ndarray:
    """channel: [time, lat, lon]. Returns same-shape array where
    out[0] = 0 and out[t] = channel[t] - channel[t-1] for t > 0."""
    out = np.zeros_like(channel)
    out[1:] = channel[1:] - channel[:-1]
    return out


def wind_speed(wind_u: np.ndarray, wind_v: np.ndarray) -> np.ndarray:
    return np.sqrt(wind_u ** 2 + wind_v ** 2)


def temporal_diff(channel: np.ndarray) -> np.ndarray:
    return _causal_diff(channel)


def spatial_gradient_magnitude(channel: np.ndarray) -> np.ndarray:
    """channel: [time, lat, lon]. Central differences in the interior,
    one-sided at the lat/lon edges — computed independently per timestep
    (never mixes information across time)."""
    grad_lat = np.gradient(channel, axis=1)
    grad_lon = np.gradient(channel, axis=2)
    return np.sqrt(grad_lat ** 2 + grad_lon ** 2)


def causal_rolling_sum(channel: np.ndarray, window_steps: int) -> np.ndarray:
    """channel: [time, lat, lon]. out[t] = sum(channel[max(0, t-window_steps+1):t+1]).
    Uses only current and past steps — never future ones."""
    n_t = channel.shape[0]
    out = np.empty_like(channel)
    cumsum = np.cumsum(channel, axis=0)
    for t in range(n_t):
        lo = max(0, t - window_steps + 1)
        out[t] = cumsum[t] - (cumsum[lo - 1] if lo > 0 else 0)
    return out


def compute_derived_features(
    base_channels: dict[str, np.ndarray],
    enabled: list[str],
    lightning_recent_count_window_steps: int,
) -> dict[str, np.ndarray]:
    """base_channels: {name: [time, lat, lon]} for every BASE_FEATURES
    name. Returns {derived_name: [time, lat, lon]} for each name in
    `enabled` (must be a subset of DERIVED_FEATURES names)."""
    out: dict[str, np.ndarray] = {}

    if "wind_speed" in enabled:
        out["wind_speed"] = wind_speed(base_channels["wind_u"], base_channels["wind_v"])
    if "cape_dt" in enabled:
        out["cape_dt"] = temporal_diff(base_channels["cape"])
    if "cin_dt" in enabled:
        out["cin_dt"] = temporal_diff(base_channels["cin"])
    if "reflectivity_dt" in enabled:
        out["reflectivity_dt"] = temporal_diff(base_channels["reflectivity"])
    if "brightness_temperature_dt" in enabled:
        out["brightness_temperature_dt"] = temporal_diff(
            base_channels["brightness_temperature"]
        )
    if "reflectivity_spatial_gradient_mag" in enabled:
        out["reflectivity_spatial_gradient_mag"] = spatial_gradient_magnitude(
            base_channels["reflectivity"]
        )
    if "lightning_recent_count_3step" in enabled:
        out["lightning_recent_count_3step"] = causal_rolling_sum(
            base_channels["lightning_strike_count"],
            lightning_recent_count_window_steps,
        )

    return out
