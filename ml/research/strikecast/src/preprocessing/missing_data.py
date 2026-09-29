"""Leakage-safe missing-data handling for time-dependent forecast inputs.

Missing values remain missing through feature construction and normalization.
The split's train-only scaler excludes them; the dense model tensor receives
the configured post-normalization fill value and retains a separate validity
mask. Windows over the configured missingness threshold are dropped.

Two-sided temporal interpolation is intentionally not used: it would make an
input at time t depend on an atmospheric observation after t.
"""

from __future__ import annotations

import numpy as np


def preserve_missing_values(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return a copy and its finite-value mask without imputing observations."""
    values = np.asarray(data).copy()
    return values, np.isfinite(values)


def interpolate_temporal_gaps(
    data: np.ndarray, max_gap_steps: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Backward-compatible name; no interpolation is done for forecast inputs.

    ``max_gap_steps`` is ignored and retained only so existing callers fail
    safe while migrating. Missing values remain NaN and invalid in the mask.
    """
    return preserve_missing_values(data)


def apply_validity_mask_fill(
    data: np.ndarray, valid_mask: np.ndarray, fill_value: float
) -> np.ndarray:
    """Fill invalid normalized values while preserving the separate mask."""
    values = np.asarray(data).copy()
    mask = np.asarray(valid_mask, dtype=bool)
    if values.shape != mask.shape:
        raise ValueError("data and valid_mask must have identical shapes")
    values[~mask] = fill_value
    return values
