"""
Phase 4 — Temporal alignment.

M1 makes no guarantee that all sources share a timestamp grid (the demo
data happens to, but docs/m1_m2_contract.md is explicit: "temporal
alignment across sources ... is M2's job"). This module:

  1. Infers (or reads from config) a common temporal resolution.
  2. Builds a common timestamp grid spanning the overlap of all sources.
  3. Maps each gridded source's [time, lat, lon, var] array onto that grid
     via nearest-neighbor timestamp matching within a small tolerance,
     leaving unmatched slots as NaN (handled later by missing_data.py).

IMPORTANT — not a leakage boundary: matching a source observation to a
common-grid slot within +/- tolerance is about reconciling small,
legitimate cross-instrument timing offsets (e.g. a satellite pass at
:02 past the hour representing the same nominal hourly slot as an NWP
analysis at :00). It never uses information from a *later* common-grid
slot to fill an *earlier* one. The actual input-time < target-time
leakage boundary is enforced downstream in sequence.py/split.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from src.ingestion.contract import DataRecord


def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _median_step_minutes(timestamps: list[str]) -> float | None:
    if len(timestamps) < 2:
        return None
    parsed = sorted(_parse_iso(t) for t in timestamps)
    deltas = [
        (b - a).total_seconds() / 60.0 for a, b in zip(parsed, parsed[1:])
    ]
    return float(np.median(deltas))


def infer_temporal_resolution_minutes(
    records: dict[str, DataRecord], configured: float | None
) -> float:
    """Use the configured resolution if given; otherwise infer the finest
    (minimum) per-source median timestep across all sources present, so
    the common grid never throws away resolution any source actually
    offers."""
    if configured is not None:
        return float(configured)

    steps = [
        _median_step_minutes(r.timestamps)
        for r in records.values()
        if r.timestamps
    ]
    steps = [s for s in steps if s is not None and s > 0]
    if not steps:
        raise ValueError(
            "Cannot infer temporal resolution: no source has 2+ timestamps "
            "and temporal_alignment.target_resolution_minutes is not set."
        )
    return float(min(steps))


def build_common_grid(
    records: dict[str, DataRecord], resolution_minutes: float
) -> list[str]:
    """Common timestamp grid spanning the INTERSECTION of all sources'
    timestamp ranges (using the overlap, not the union, avoids inventing
    slots where some source has no chance of ever having data)."""
    starts = [_parse_iso(r.timestamps[0]) for r in records.values() if r.timestamps]
    ends = [_parse_iso(r.timestamps[-1]) for r in records.values() if r.timestamps]
    if not starts or not ends:
        raise ValueError("Cannot build a common temporal grid: no source has timestamps.")

    grid_start = max(starts)
    grid_end = min(ends)
    if grid_start > grid_end:
        raise ValueError(
            f"Sources have no temporal overlap: latest start={grid_start.isoformat()}, "
            f"earliest end={grid_end.isoformat()}."
        )

    step = timedelta(minutes=resolution_minutes)
    grid = []
    t = grid_start
    while t <= grid_end:
        grid.append(_format_iso(t))
        t += step
    return grid


def align_gridded_source(
    record: DataRecord,
    common_grid: list[str],
    tolerance_minutes: float,
) -> np.ndarray:
    """Nearest-neighbor-match `record.data` [time, lat, lon, var] onto
    `common_grid`. Unmatched common-grid slots (no source observation
    within tolerance) are filled with NaN across all variables/cells —
    a real absence, not an invented value; missing_data.py decides how
    (or whether) to fill it later."""
    if record.data is None:
        raise ValueError(f"align_gridded_source requires a gridded record, got {record.source}")

    src_times = [_parse_iso(t) for t in record.timestamps]
    grid_times = [_parse_iso(t) for t in common_grid]
    tol = timedelta(minutes=tolerance_minutes)

    n_lat, n_lon, n_var = record.data.shape[1], record.data.shape[2], record.data.shape[3]
    out = np.full((len(common_grid), n_lat, n_lon, n_var), np.nan, dtype=np.float32)

    if not src_times:
        return out

    src_times_arr = np.array([t.timestamp() for t in src_times])
    for i, gt in enumerate(grid_times):
        gt_s = gt.timestamp()
        j = int(np.argmin(np.abs(src_times_arr - gt_s)))
        if abs(src_times[j] - gt) <= tol:
            out[i] = record.data[j]

    return out


def align_point_source_timestamps(
    point_data: list[dict],
    common_grid: list[str],
    tolerance_minutes: float,
) -> list[dict]:
    """Assign each point to the first common-grid time at or after its event.

    Rounding to the nearest slot can move an event backward and leak it into
    a forecast input timestamp before the observation occurred. Ceiling to a
    causal slot avoids that look-ahead; points outside tolerance are dropped.
    """
    if not point_data:
        return []

    grid_times = [_parse_iso(t) for t in common_grid]
    grid_times_arr = np.array([t.timestamp() for t in grid_times])
    tol = timedelta(minutes=tolerance_minutes).total_seconds()

    out = []
    for p in point_data:
        pt = _parse_iso(p["timestamp"]).timestamp()
        j = int(np.searchsorted(grid_times_arr, pt, side="left"))
        if j < len(grid_times_arr) and grid_times_arr[j] - pt <= tol:
            p2 = dict(p)
            p2["timestamp"] = common_grid[j]
            out.append(p2)
    return out
