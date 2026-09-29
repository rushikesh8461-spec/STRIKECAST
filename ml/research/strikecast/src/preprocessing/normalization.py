"""
Phase 7 — Normalization.

Critical rule (spec Phase 7, restated): mean/std must be computed from
the TRAINING split only, then applied unchanged to train/val/test/
inference. This module never looks at val/test data when fitting stats,
and persists stats to disk so inference can reuse the exact training-time
values (reproducibility, Phase 13).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def fit_normalization_stats(
    train_tensor: np.ndarray,
    valid_mask: np.ndarray,
    feature_names: list[str],
    std_floor: float,
) -> dict:
    """
    train_tensor: [time, lat, lon, channel] — TRAIN SPLIT INPUT TIMES ONLY.
    valid_mask: same shape, bool — True only for observed train values.
        Missing values are never interpolated and do not pollute statistics.
    Returns {channel_name: {"mean": float, "std": float}}.
    """
    if train_tensor.shape[-1] != len(feature_names):
        raise ValueError(
            f"train_tensor has {train_tensor.shape[-1]} channels but "
            f"{len(feature_names)} feature_names were given."
        )
    stats = {}
    for c, name in enumerate(feature_names):
        channel_vals = train_tensor[..., c][valid_mask[..., c]]
        if channel_vals.size == 0:
            # No valid training observation for this channel at all —
            # cannot compute real statistics; document rather than fake it.
            mean, std = 0.0, 1.0
        else:
            mean = float(np.mean(channel_vals))
            std = float(np.std(channel_vals))
            if std < std_floor:
                std = std_floor
        stats[name] = {"mean": mean, "std": std}
    return stats


def apply_normalization(
    tensor: np.ndarray, feature_names: list[str], stats: dict
) -> np.ndarray:
    """z-score each channel using previously-fit (TRAIN-only) stats.
    Safe to call on train, val, test, or inference data — the stats
    passed in are always the same, frozen, training-time values."""
    if tensor.shape[-1] != len(feature_names):
        raise ValueError(
            f"tensor has {tensor.shape[-1]} channels but "
            f"{len(feature_names)} feature_names were given."
        )
    out = tensor.copy()
    for c, name in enumerate(feature_names):
        s = stats[name]
        out[..., c] = (out[..., c] - s["mean"]) / s["std"]
    return out


def save_normalization_stats(stats: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(stats, f, indent=2)


def load_normalization_stats(path: Path) -> dict:
    with open(Path(path), "r") as f:
        return json.load(f)
