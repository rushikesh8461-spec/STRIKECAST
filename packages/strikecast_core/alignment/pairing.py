"""Deterministic pairing of provider-normalized ERA5 and LIS observations.

This module consumes canonical records. It does not interpret product-specific
NetCDF quality flags; adapters must resolve quality to ``observed`` explicitly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_pair_index(atmospheric: Iterable[dict], observations: Iterable[dict], *,
                     atmospheric_version: str, lightning_version: str) -> list[dict]:
    """Return stable sample rows; absent/unobserved LIS is always UNKNOWN.

    Atmospheric rows require ``timestamp_utc``, ``cell_id``, ``available``,
    and ``source_sha256``. Observation rows require the same time/cell keys,
    explicit Boolean ``observed`` and ``lightning_detected``, quality metadata,
    and source hash. The caller supplies one row per desired LIS cell/time.
    """
    if not atmospheric_version or not lightning_version:
        raise ValueError("Both provider dataset versions are required")
    atmos_index = {}
    for row in atmospheric:
        key = (_utc(row["timestamp_utc"]), str(row["cell_id"]))
        if key in atmos_index:
            raise ValueError(f"duplicate atmospheric record at {key}")
        if not isinstance(row.get("available"), bool):
            raise ValueError("atmospheric availability must be explicit Boolean")
        atmos_index[key] = row

    observation_index = {}
    for row in observations:
        key = (_utc(row["timestamp_utc"]), str(row["cell_id"]))
        if key in observation_index:
            raise ValueError(f"duplicate LIS observation record at {key}")
        if not isinstance(row.get("observed"), bool):
            raise ValueError("LIS observed coverage must be explicit Boolean")
        if not isinstance(row.get("lightning_detected"), bool):
            raise ValueError("LIS lightning detection must be explicit Boolean")
        if not row.get("quality_flags"):
            raise ValueError("quality flags must be preserved for every LIS row")
        observation_index[key] = row

    rows = []
    for key in sorted(set(atmos_index) | set(observation_index)):
        atmo, lis = atmos_index.get(key), observation_index.get(key)
        if lis is None or lis["observed"] is False:
            status = "UNKNOWN"
        elif lis["lightning_detected"]:
            status = "POSITIVE"
        else:
            status = "NEGATIVE"
        rows.append({
            "timestamp_utc": key[0].isoformat(), "cell_id": key[1],
            "atmospheric_feature_available": bool(atmo and atmo["available"]),
            "target_status": status,
            "source_sha256": {"era5": atmo.get("source_sha256") if atmo else None,
                              "lis": lis.get("source_sha256") if lis else None},
            "dataset_versions": {"era5": atmospheric_version, "lis": lightning_version},
            "quality_flags": lis.get("quality_flags") if lis else ["NO_LIS_COVERAGE"],
        })
    return rows
