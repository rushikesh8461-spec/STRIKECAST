"""Temporal validation (Phase 6): timestamps, ordering, duplicates, gaps."""

from __future__ import annotations

from datetime import datetime, timezone


def _parse_iso(ts: str) -> datetime:
    # Accepts "...Z" suffix as UTC.
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp '{ts}' is not timezone-aware (UTC required).")
    return dt.astimezone(timezone.utc)


def validate_temporal(
    timestamps: list[str],
    expected_timestep_minutes: int | None = None,
) -> dict:
    """
    Returns a dict:
        valid: bool
        issues: list[str]
        n_timestamps: int
        n_duplicates: int
        is_chronological: bool
        gaps: list[dict]  -- {after, before, gap_minutes} for unexpected gaps
        coverage_fraction: float (1.0 if expected_timestep_minutes is None)
    """
    issues: list[str] = []
    parsed: list[datetime] = []

    for ts in timestamps:
        try:
            parsed.append(_parse_iso(ts))
        except ValueError as e:
            issues.append(str(e))

    if len(parsed) != len(timestamps):
        # Some timestamps failed to parse; can't reliably continue ordering checks.
        return {
            "valid": False,
            "issues": issues or ["One or more timestamps failed to parse."],
            "n_timestamps": len(timestamps),
            "n_duplicates": None,
            "is_chronological": False,
            "gaps": [],
            "coverage_fraction": 0.0,
            "timestamp_start": timestamps[0] if timestamps else "",
            "timestamp_end": timestamps[-1] if timestamps else "",
        }

    n_duplicates = len(parsed) - len(set(parsed))
    if n_duplicates > 0:
        issues.append(f"{n_duplicates} duplicate timestamp(s) found.")

    is_chronological = parsed == sorted(parsed)
    if not is_chronological:
        issues.append("Timestamps are not in chronological order.")

    gaps = []
    coverage_fraction = 1.0
    if expected_timestep_minutes and len(parsed) > 1:
        sorted_parsed = sorted(parsed)
        expected_seconds = expected_timestep_minutes * 60
        n_expected_gaps = 0
        n_matched_gaps = 0
        for a, b in zip(sorted_parsed, sorted_parsed[1:]):
            gap_seconds = (b - a).total_seconds()
            n_expected_gaps += 1
            # allow small tolerance (10% of a timestep) for jitter
            tolerance = expected_seconds * 0.1
            if abs(gap_seconds - expected_seconds) > tolerance:
                gaps.append(
                    {
                        "after": a.isoformat(),
                        "before": b.isoformat(),
                        "gap_minutes": gap_seconds / 60.0,
                    }
                )
            else:
                n_matched_gaps += 1
        if n_expected_gaps > 0:
            coverage_fraction = n_matched_gaps / n_expected_gaps
        if gaps:
            issues.append(f"{len(gaps)} unexpected temporal gap(s) detected.")

    valid = n_duplicates == 0 and is_chronological and not gaps

    return {
        "valid": valid,
        "issues": issues,
        "n_timestamps": len(timestamps),
        "n_duplicates": n_duplicates,
        "is_chronological": is_chronological,
        "gaps": gaps,
        "coverage_fraction": coverage_fraction,
        "timestamp_start": timestamps[0] if timestamps else "",
        "timestamp_end": timestamps[-1] if timestamps else "",
    }
