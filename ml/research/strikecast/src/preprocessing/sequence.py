"""
Phase 9 — Sequence/window construction.

    t-L+1 ... t          input sequence  (indices [s, s+L))
    t+1   ... t+H         target          (indices [s+L, s+L+H))

This module is the single place that decides which timestamps are
"input" and which are "target" for a given window — the leakage
guarantee INPUT TIME < TARGET TIME (Phase 10) reduces to the simple
arithmetic fact that every target index (s+L .. s+L+H-1) is strictly
greater than every input index (s .. s+L-1), which holds for any
non-negative L, H by construction and is asserted by
tests/preprocessing/test_no_temporal_leakage.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Window:
    start: int              # first input index (inclusive)
    input_end: int           # last input index + 1 (exclusive) == start + L
    target_end: int          # last target index + 1 (exclusive) == start + L + H

    @property
    def input_indices(self) -> range:
        return range(self.start, self.input_end)

    @property
    def target_indices(self) -> range:
        return range(self.input_end, self.target_end)

    @property
    def full_indices(self) -> range:
        return range(self.start, self.target_end)


def build_windows(
    n_timesteps: int, sequence_length: int, forecast_horizon: int, stride: int
) -> list[Window]:
    if sequence_length < 1 or forecast_horizon < 1 or stride < 1:
        raise ValueError("sequence_length, forecast_horizon, and stride must all be >= 1.")

    window_size = sequence_length + forecast_horizon
    windows = []
    start = 0
    while start + window_size <= n_timesteps:
        windows.append(
            Window(
                start=start,
                input_end=start + sequence_length,
                target_end=start + window_size,
            )
        )
        start += stride
    return windows
