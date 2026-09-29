"""
Phase 10 — Target/label construction.

TARGET DEFINITION — read this first (also see docs/m2_m3_contract.md):
No target definition existed anywhere in this repository (no M3/M4 code,
no spec document pins one down) — Phase 1 audit: MISSING — NOT PRESENT IN
REPOSITORY. Per the instructions ("do not invent a target definition if
one already exists" / "if it does not exist, state so and define one
explicitly, MVP-appropriate"), M2 defines the MVP target as:

    Y[h, lat, lon] = 1 if lightning_strike_count[target_time_h, lat, lon]
                        >= target.occurrence_threshold_strikes
                     else 0

i.e. gridded, per-cell, per-future-step binary lightning occurrence,
matching the conceptual shape given in the brief:
    Y = [batch, forecast_horizon, latitude, longitude]
A continuous alternative (raw strike_count, `target.mode: "strike_count"`)
is also supported for M4/M3 experiments that want a regression target
instead of a classification one. This is an M2 assumption, not a
requirement handed down from another member — confirm it matches what M3
(model output head) and M4 (evaluation/calibration) actually need before
relying on it for anything beyond the MVP.

Leakage rule (Phase 10, enforced here and re-checked in split.py): the
strike_count/target array is built from the SAME gridded lightning tensor
used as an M2 *input* feature (lightning_strike_count), but a given
window's target only ever reads timesteps strictly after that window's
input timesteps — see sequence.py, which is the single place that decides
which time indices are "input" vs "target".
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import IntEnum


class ObservationState(IntEnum):
    UNKNOWN = 0
    NEGATIVE = 1
    POSITIVE = 2


@dataclass(frozen=True)
class MaskedTarget:
    values: np.ndarray
    observation_mask: np.ndarray
    states: np.ndarray


def build_observation_aware_target(
    event_count: np.ndarray,
    observation_mask: np.ndarray,
    quality_mask: np.ndarray | None = None,
    occurrence_threshold: int = 1,
) -> MaskedTarget:
    """Build cell targets without converting unobserved coverage to negatives.

    ``observation_mask`` must mean that the sensor had sufficient valid view
    time for the complete target interval. ``quality_mask`` further excludes
    cells failing the versioned quality policy. ``values`` is 0 where UNKNOWN
    only as a storage placeholder; consumers MUST use observation_mask.
    """
    counts = np.asarray(event_count)
    observed = np.asarray(observation_mask, dtype=bool)
    if counts.shape != observed.shape:
        raise ValueError("event_count and observation_mask must have identical shapes")
    if occurrence_threshold < 1:
        raise ValueError("occurrence_threshold must be >= 1")
    if quality_mask is None:
        quality = np.ones(counts.shape, dtype=bool)
    else:
        quality = np.asarray(quality_mask, dtype=bool)
        if quality.shape != counts.shape:
            raise ValueError("quality_mask must match event_count shape")
    usable = observed & quality & np.isfinite(counts) & (counts >= 0)
    states = np.full(counts.shape, ObservationState.UNKNOWN, dtype=np.uint8)
    states[usable & (counts < occurrence_threshold)] = ObservationState.NEGATIVE
    states[usable & (counts >= occurrence_threshold)] = ObservationState.POSITIVE
    values = np.zeros(counts.shape, dtype=np.float32)
    values[states == ObservationState.POSITIVE] = 1.0
    return MaskedTarget(values=values, observation_mask=usable, states=states)


def build_target_grid(
    lightning_strike_count: np.ndarray, mode: str, occurrence_threshold: int
) -> np.ndarray:
    """Legacy unmasked helper for presentation/demo fixtures only.

    It cannot distinguish an observed zero from an unobserved cell and MUST
    NOT be used to create real-data negatives. Real target construction uses
    :func:`build_observation_aware_target`.

    lightning_strike_count: [time, lat, lon] (already temporally +
    spatially aligned — the same array feature_pipeline uses as an input
    channel). Returns the full-timeline target grid [time, lat, lon];
    sequence.py slices out the future steps for each window."""
    if mode == "occurrence":
        return (lightning_strike_count >= occurrence_threshold).astype(np.float32)
    elif mode == "strike_count":
        return lightning_strike_count.astype(np.float32)
    else:
        raise ValueError(f"Unknown target.mode '{mode}' (expected 'occurrence' or 'strike_count').")
