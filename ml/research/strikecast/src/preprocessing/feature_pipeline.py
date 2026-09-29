"""
Ties spatial_alignment + missing_data + src.features.engineering together
into one fixed-channel-order feature tensor with a matching per-channel
validity mask. This is the module that actually builds the array M2 hands
to sequence.py.

Design: base channels are aligned/cleaned first (Phases 4-6); derived
channels (Phase 8) are computed from the *cleaned* base channels so a
derived feature's own validity can be expressed as a documented function
of its inputs' validity, rather than silently inheriting NaNs.
"""

from __future__ import annotations

import numpy as np

from src.features import engineering
from src.features.schema import BASE_FEATURES, resolve_channel_order

from .missing_data import preserve_missing_values


def stack_base_channels(
    channel_arrays: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[str]]:
    """channel_arrays: {base_feature_name: [time, lat, lon]}, one entry per
    name in BASE_FEATURES (schema.py) — caller is responsible for having
    already aligned every source onto the same common grid/timestamps and
    gridded lightning (spatial_alignment.bin_lightning_to_grid). Returns
    (base_tensor [time, lat, lon, C_base], base_names) in the fixed
    BASE_FEATURES order."""
    base_names = [f.name for f in BASE_FEATURES]
    missing = [n for n in base_names if n not in channel_arrays]
    if missing:
        raise ValueError(f"Missing required base channel(s): {missing}")
    stacked = np.stack([channel_arrays[n] for n in base_names], axis=-1)
    return stacked.astype(np.float32), base_names


def clean_base_tensor(base_tensor: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Preserve missing values; two-sided interpolation leaks future values.

    Missing values remain masked for the explicit post-normalization fill.
    """
    return preserve_missing_values(base_tensor)


def _shifted_valid(valid_1ch: np.ndarray) -> np.ndarray:
    """Validity for a causal diff: out[0]=True (defined as 0, always
    valid); out[t] = valid[t] & valid[t-1] for t > 0."""
    out = np.ones_like(valid_1ch)
    out[1:] = valid_1ch[1:] & valid_1ch[:-1]
    return out


def _rolling_valid(valid_1ch: np.ndarray, window_steps: int) -> np.ndarray:
    """Validity for a causal rolling sum: valid at t only if every step in
    the window [max(0, t-window+1), t] is valid (conservative — any gap in
    the window invalidates the whole rolling value, since the sum has no
    principled partial-window estimate to fall back on)."""
    n_t = valid_1ch.shape[0]
    out = np.zeros_like(valid_1ch)
    for t in range(n_t):
        lo = max(0, t - window_steps + 1)
        out[t] = np.all(valid_1ch[lo : t + 1], axis=0)
    return out


def compute_derived_with_validity(
    base_names: list[str],
    filled_base: np.ndarray,
    base_valid: np.ndarray,
    enabled_derived: list[str],
    lightning_recent_count_window_steps: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Returns (derived_arrays, derived_valid) each keyed by derived
    feature name, computed from the cleaned (but possibly still-NaN)
    base tensor. NaNs remaining after preserving missingness are filled ONLY
    for the arithmetic (so e.g. a diff doesn't propagate NaN indefinitely
    through later, otherwise-valid steps) — the corresponding validity
    array is what actually tracks trustworthiness downstream, exactly as
    for base channels."""
    idx = {n: i for i, n in enumerate(base_names)}
    calc_safe = np.nan_to_num(filled_base, nan=0.0)

    def ch(name):
        return calc_safe[..., idx[name]]

    def v(name):
        return base_valid[..., idx[name]]

    channel_dict = {n: ch(n) for n in base_names}
    derived_arrays = engineering.compute_derived_features(
        channel_dict, enabled_derived, lightning_recent_count_window_steps
    )

    derived_valid: dict[str, np.ndarray] = {}
    if "wind_speed" in enabled_derived:
        derived_valid["wind_speed"] = v("wind_u") & v("wind_v")
    if "cape_dt" in enabled_derived:
        derived_valid["cape_dt"] = _shifted_valid(v("cape"))
    if "cin_dt" in enabled_derived:
        derived_valid["cin_dt"] = _shifted_valid(v("cin"))
    if "reflectivity_dt" in enabled_derived:
        derived_valid["reflectivity_dt"] = _shifted_valid(v("reflectivity"))
    if "brightness_temperature_dt" in enabled_derived:
        derived_valid["brightness_temperature_dt"] = _shifted_valid(
            v("brightness_temperature")
        )
    if "reflectivity_spatial_gradient_mag" in enabled_derived:
        # Approximation (documented): a spatial gradient technically also
        # depends on neighboring cells' validity, not just the cell's own.
        # We conservatively use the cell's own validity as a proxy rather
        # than tracking full neighbor provenance, which is judged
        # sufficient for the MVP (Phase 15: correctness > premature
        # completeness for a second-order derived feature).
        derived_valid["reflectivity_spatial_gradient_mag"] = v("reflectivity")
    if "lightning_recent_count_3step" in enabled_derived:
        derived_valid["lightning_recent_count_3step"] = _rolling_valid(
            v("lightning_strike_count"), lightning_recent_count_window_steps
        )

    return derived_arrays, derived_valid


def build_feature_tensor(
    channel_arrays: dict[str, np.ndarray],
    enabled_derived: list[str],
    lightning_recent_count_window_steps: int,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Top-level Phase 6+8 entry point. Returns
    (feature_tensor_with_nan, valid_mask, channel_names) where
    feature_tensor_with_nan still has NaN wherever valid_mask is False
    (normalization.py and missing_data.apply_validity_mask_fill decide
    what happens to those NaNs next)."""
    base_tensor, base_names = stack_base_channels(channel_arrays)
    filled_base, base_valid = clean_base_tensor(base_tensor)

    derived_arrays, derived_valid = compute_derived_with_validity(
        base_names, filled_base, base_valid, enabled_derived,
        lightning_recent_count_window_steps,
    )

    channel_order = resolve_channel_order(enabled_derived)
    all_arrays = {**{n: filled_base[..., i] for i, n in enumerate(base_names)}, **derived_arrays}
    all_valid = {**{n: base_valid[..., i] for i, n in enumerate(base_names)}, **derived_valid}

    tensor = np.stack([all_arrays[n] for n in channel_order], axis=-1).astype(np.float32)
    valid = np.stack([all_valid[n] for n in channel_order], axis=-1)
    tensor = np.where(valid, tensor, np.nan)

    return tensor, valid, channel_order
