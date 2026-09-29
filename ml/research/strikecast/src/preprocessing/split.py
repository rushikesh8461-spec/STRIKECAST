"""
Phase 11 — Train/validation/test splitting.

Chronological split (PAST -> TRAIN, LATER -> VALIDATION, LATEST -> TEST),
computed on the *timestamp index range*, not on window count — window
count is a downstream consequence, not the split criterion. A window
(sequence.Window) is assigned to a split only if its ENTIRE
input+target index range (window.full_indices) lies within that split's
index range; a window straddling a split boundary is DROPPED, never
duplicated and never truncated into either side. This is what prevents:
  - temporal leakage (a train window's target reaching into val/test time)
  - overlapping-window duplication across splits
  - normalization leakage (normalization.py only ever sees TRAIN windows)

With very few timesteps (see the bundled 12-step demo dataset) a given
split's index range can be shorter than one full window, so that split
legitimately gets zero windows — this function does not force non-empty
splits by fabricating overlap; see docs/m2_m3_contract.md "Known
limitations" for how this shows up on the bundled demo data and how to
avoid it for real training.
"""

from __future__ import annotations

from dataclasses import dataclass

from .sequence import Window


@dataclass(frozen=True)
class SplitBoundaries:
    train_end: int   # exclusive
    val_end: int      # exclusive; train_end:val_end is the val range
    n_timesteps: int  # val_end:n_timesteps is the test range


def compute_split_boundaries(
    n_timesteps: int, train_fraction: float, val_fraction: float, test_fraction: float
) -> SplitBoundaries:
    total = train_fraction + val_fraction + test_fraction
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"split fractions must sum to 1.0, got {total} "
            f"(train={train_fraction}, val={val_fraction}, test={test_fraction})"
        )
    train_end = round(train_fraction * n_timesteps)
    val_end = round((train_fraction + val_fraction) * n_timesteps)
    train_end = max(0, min(train_end, n_timesteps))
    val_end = max(train_end, min(val_end, n_timesteps))
    return SplitBoundaries(train_end=train_end, val_end=val_end, n_timesteps=n_timesteps)


def _fully_within(window: Window, lo: int, hi: int) -> bool:
    return window.start >= lo and window.target_end <= hi


def assign_windows_to_splits(
    windows: list[Window], boundaries: SplitBoundaries
) -> dict[str, list[Window]]:
    train, val, test, dropped = [], [], [], []
    for w in windows:
        if _fully_within(w, 0, boundaries.train_end):
            train.append(w)
        elif _fully_within(w, boundaries.train_end, boundaries.val_end):
            val.append(w)
        elif _fully_within(w, boundaries.val_end, boundaries.n_timesteps):
            test.append(w)
        else:
            dropped.append(w)  # straddles a split boundary
    return {"train": train, "val": val, "test": test, "_dropped": dropped}
