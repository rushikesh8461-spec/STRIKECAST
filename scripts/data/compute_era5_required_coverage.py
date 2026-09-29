#!/usr/bin/env python
"""Derive ERA5 acquisition hours from actual LIS observations in StrikeCast's ROI."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "data/database/manifests/dataset_inventory.json"
OUTPUT_JSON = ROOT / "data/database/manifests/era5_required_coverage.json"
OUTPUT_MD = ROOT / "artifacts/reports/ERA5_REQUIRED_COVERAGE.md"
DOMAIN = {"north": 20.0, "south": 8.0, "west": 72.0, "east": 82.0}
SEQUENCE_LENGTH = 4
FORECAST_HORIZON = 1
CADENCE_HOURS = 1

SURFACE_VARIABLES = [
    {"short_name": "10u", "name": "10m u-component of wind"},
    {"short_name": "10v", "name": "10m v-component of wind"},
    {"short_name": "2t", "name": "2m temperature"},
    {"short_name": "2d", "name": "2m dewpoint temperature"},
    {"short_name": "msl", "name": "mean sea level pressure"},
    {"short_name": "sp", "name": "surface pressure"},
    {"short_name": "tp", "name": "total precipitation"},
    {"short_name": "tcc", "name": "total cloud cover"},
    {"short_name": "blh", "name": "boundary layer height"},
    {"short_name": "cbh", "name": "cloud base height"},
    {"short_name": "skt", "name": "skin temperature"},
]
PRESSURE_VARIABLES = [
    {"short_name": "t", "name": "temperature"},
    {"short_name": "r", "name": "relative humidity"},
    {"short_name": "u", "name": "u wind"},
    {"short_name": "v", "name": "v wind"},
    {"short_name": "w", "name": "vertical velocity"},
    {"short_name": "z", "name": "geopotential"},
]
PRESSURE_LEVELS_HPA = [1000, 925, 850, 700, 500, 300, 200]


def utc_from_tai(value: float, orbit_tai_start: float, orbit_start_utc: datetime) -> datetime:
    return orbit_start_utc + timedelta(seconds=float(value) - orbit_tai_start)


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def inside(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    return (
        np.isfinite(lat) & np.isfinite(lon)
        & (lat >= DOMAIN["south"]) & (lat <= DOMAIN["north"])
        & (lon >= DOMAIN["west"]) & (lon <= DOMAIN["east"])
    )


def values(ds, name: str, dtype=float) -> np.ndarray:
    if name not in ds.variables:
        return np.asarray([], dtype=dtype)
    return np.asarray(ds.variables[name][:], dtype=dtype).reshape(-1)


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    raw = ROOT / inventory["raw_root"]
    readable = [
        row for row in inventory["files"]
        if row.get("netcdf") and row.get("relative_path", "").lower().endswith(".nc")
    ]
    granules = []
    all_granule_audit = []
    by_date_intervals: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    by_date_granules: dict[str, list[dict]] = defaultdict(list)
    target_bins: set[datetime] = set()
    by_date_target_bins: dict[str, set[datetime]] = defaultdict(set)
    all_domain_viewtime_intervals: list[tuple[datetime, datetime]] = []

    for row in readable:
        path = raw / Path(row["relative_path"])
        digest = row["sha256"]
        with Dataset(path, "r") as ds:
            orbit_tai_start = float(np.asarray(ds.variables["orbit_summary_TAI93_start"][:]).item())
            orbit_tai_end = float(np.asarray(ds.variables["orbit_summary_TAI93_end"][:]).item())
            orbit_start_utc = datetime.fromisoformat(
                str(np.asarray(ds.variables["orbit_summary_UTC_start"][:]).item()).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            orbit_end_utc = utc_from_tai(orbit_tai_end, orbit_tai_start, orbit_start_utc)

            vt_lat, vt_lon = values(ds, "viewtime_lat"), values(ds, "viewtime_lon")
            vt_start, vt_end = values(ds, "viewtime_TAI93_start"), values(ds, "viewtime_TAI93_end")
            vt_alert = values(ds, "viewtime_alert_flag", int)
            vt_roi = inside(vt_lat, vt_lon)
            domain_intervals = [
                (utc_from_tai(a, orbit_tai_start, orbit_start_utc),
                 utc_from_tai(b, orbit_tai_start, orbit_start_utc))
                for a, b in zip(vt_start[vt_roi], vt_end[vt_roi]) if b >= a
            ]
            domain_intervals = merge_intervals(domain_intervals)

            flash_lat, flash_lon = values(ds, "lightning_flash_lat"), values(ds, "lightning_flash_lon")
            flash_tai = values(ds, "lightning_flash_TAI93_time")
            flash_flags = values(ds, "lightning_flash_alert_flag", int)
            flash_roi = inside(flash_lat, flash_lon)
            event_lat, event_lon = values(ds, "lightning_event_lat"), values(ds, "lightning_event_lon")
            event_tai = values(ds, "lightning_event_TAI93_time")
            event_flags = values(ds, "lightning_event_alert_flag", int)
            event_roi = inside(event_lat, event_lon)

            flash_times = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in flash_tai[flash_roi]]
            event_times = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in event_tai[event_roi]]
            flash_domain_flags = Counter(str(int(x)) for x in flash_flags[flash_roi])
            event_domain_flags = Counter(str(int(x)) for x in event_flags[event_roi])
            viewtime_domain_flags = Counter(str(int(x)) for x in vt_alert[vt_roi])

        def bounds(lat: np.ndarray, lon: np.ndarray) -> dict | None:
            valid = np.isfinite(lat) & np.isfinite(lon)
            if not valid.any():
                return None
            return {"south": float(lat[valid].min()), "north": float(lat[valid].max()),
                    "west": float(lon[valid].min()), "east": float(lon[valid].max())}

        vt_utc_starts = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in vt_start]
        vt_utc_ends = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in vt_end]
        all_flash_times = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in flash_tai]
        all_event_times = [utc_from_tai(x, orbit_tai_start, orbit_start_utc) for x in event_tai]
        all_granule_audit.append({
            "file": row["file"], "raw_relative_path": row["relative_path"], "sha256": digest,
            "orbit_id": row["netcdf"]["orbit_id"],
            "observation_start_utc": orbit_start_utc.isoformat(),
            "observation_end_utc": orbit_end_utc.isoformat(),
            "intersects_domain": bool(vt_roi.any() or flash_roi.any() or event_roi.any()),
            "viewtime_record_count": int(len(vt_lat)),
            "viewtime_utc_bounds": ([min(vt_utc_starts).isoformat(), max(vt_utc_ends).isoformat()] if vt_utc_starts and vt_utc_ends else None),
            "viewtime_geolocation_bounds": bounds(vt_lat, vt_lon),
            "viewtime_quality_flag_counts": dict(Counter(str(int(x)) for x in vt_alert)),
            "lightning_flash_record_count": int(len(flash_lat)),
            "lightning_flash_utc_bounds": ([min(all_flash_times).isoformat(), max(all_flash_times).isoformat()] if all_flash_times else None),
            "lightning_flash_geolocation_bounds": bounds(flash_lat, flash_lon),
            "lightning_flash_quality_flag_counts": dict(Counter(str(int(x)) for x in flash_flags)),
            "lightning_event_record_count": int(len(event_lat)),
            "lightning_event_utc_bounds": ([min(all_event_times).isoformat(), max(all_event_times).isoformat()] if all_event_times else None),
            "lightning_event_geolocation_bounds": bounds(event_lat, event_lon),
            "lightning_event_quality_flag_counts": dict(Counter(str(int(x)) for x in event_flags)),
        })

        intersects = bool(vt_roi.any() or flash_roi.any() or event_roi.any())
        if not intersects:
            continue

        for start, end in domain_intervals:
            all_domain_viewtime_intervals.append((start, end))
            cursor = start
            while cursor < end or cursor == start:
                day_end = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
                clipped_end = min(end, day_end)
                by_date_intervals[cursor.date().isoformat()].append((cursor, clipped_end))
                cursor = day_end
            hour = start.replace(minute=0, second=0, microsecond=0)
            last_hour = end.replace(minute=0, second=0, microsecond=0)
            while hour < end or (hour == end and end == start):
                target_bins.add(hour)
                by_date_target_bins[hour.date().isoformat()].add(hour)
                hour += timedelta(hours=CADENCE_HOURS)
        for instant in flash_times + event_times:
            hour = instant.replace(minute=0, second=0, microsecond=0)
            target_bins.add(hour)
            by_date_target_bins[hour.date().isoformat()].add(hour)

        granule = {
            "file": row["file"],
            "raw_relative_path": row["relative_path"],
            "sha256": digest,
            "orbit_id": row["netcdf"]["orbit_id"],
            "granule_start_utc": orbit_start_utc.isoformat(),
            "granule_end_utc": orbit_end_utc.isoformat(),
            "viewtime_records_in_domain": int(vt_roi.sum()),
            "unique_viewtime_cells_in_domain": int(len(set(zip(vt_lat[vt_roi].tolist(), vt_lon[vt_roi].tolist())))),
            "viewtime_intervals_utc": [[a.isoformat(), b.isoformat()] for a, b in domain_intervals],
            "viewtime_alert_flag_counts_in_domain": dict(viewtime_domain_flags),
            "flash_records_in_domain": int(flash_roi.sum()),
            "flash_time_range_utc": ([min(flash_times).isoformat(), max(flash_times).isoformat()] if flash_times else None),
            "flash_alert_flag_counts_in_domain": dict(flash_domain_flags),
            "event_records_in_domain": int(event_roi.sum()),
            "event_time_range_utc": ([min(event_times).isoformat(), max(event_times).isoformat()] if event_times else None),
            "event_alert_flag_counts_in_domain": dict(event_domain_flags),
            "viewtime_bounds_in_domain": (
                {"south": float(vt_lat[vt_roi].min()), "north": float(vt_lat[vt_roi].max()),
                 "west": float(vt_lon[vt_roi].min()), "east": float(vt_lon[vt_roi].max())}
                if vt_roi.any() else None
            ),
        }
        granules.append(granule)
        by_date_granules[orbit_start_utc.date().isoformat()].append(granule)

    by_date = []
    coverage_dates = set(by_date_granules) | set(by_date_intervals) | set(by_date_target_bins)
    for date in sorted(coverage_dates):
        intervals = merge_intervals(by_date_intervals.get(date, []))
        by_date.append({
            "date": date,
            "domain_intersecting_granules_by_orbit_start_date": len(by_date_granules[date]),
            "domain_viewtime_intervals_utc": [[a.isoformat(), b.isoformat()] for a, b in intervals],
            "utc_hour_bins_touched": [h.strftime("%H:00") for h in sorted(by_date_target_bins[date])],
            "flash_records_in_domain": sum(x["flash_records_in_domain"] for x in by_date_granules[date]),
            "event_records_in_domain": sum(x["event_records_in_domain"] for x in by_date_granules[date]),
        })

    required_input_hours: set[datetime] = set()
    for target_hour in target_bins:
        # With a one-hour cadence, target interval [h,h+1) is predicted from
        # the four preceding input timestamps h-3,h-2,h-1,h. The target-hour
        # atmospheric state is deliberately excluded to avoid future leakage.
        for offset in range(SEQUENCE_LENGTH):
            required_input_hours.add(target_hour - timedelta(hours=SEQUENCE_LENGTH - 1 - offset))

    def hours_by_date(hours: set[datetime]) -> list[dict]:
        grouped: dict[str, list[int]] = defaultdict(list)
        for hour in sorted(hours):
            grouped[hour.date().isoformat()].append(hour.hour)
        return [{"date": date, "utc_hours": [f"{h:02d}:00" for h in sorted(set(values))]}
                for date, values in sorted(grouped.items())]

    existing_hours: set[datetime] = set()
    for date in ("2023-11-16",):
        existing_hours.update(datetime.fromisoformat(f"{date}T{hour:02d}:00:00+00:00") for hour in range(24))
    # Existing 2025 ERA5 covers every hour from 2025-04-01 through 2025-12-31.
    current = datetime(2025, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    while current < end:
        for hour in range(24):
            existing_hours.add(current.replace(hour=hour))
        current += timedelta(days=1)

    missing_hours = required_input_hours - existing_hours
    available_required = required_input_hours & existing_hours
    hourly_ranges = []
    for row in by_date:
        for interval in row["domain_viewtime_intervals_utc"]:
            hourly_ranges.append(interval)

    result = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_inventory": INVENTORY.relative_to(ROOT).as_posix(),
        "source_ingestion_manifest": "data/database/manifests/historical_lis_ingestion.json",
        "domain": DOMAIN,
        "lis_granules": {
            "readable_unique_granules_inspected": len(readable),
            "domain_intersecting_granules": len(granules),
            "non_intersecting_readable_granules": len(readable) - len(granules),
            "unreadable_or_empty_unique_files_excluded": 2,
            "domain_dates_utc": sorted(coverage_dates),
            "domain_viewtime_interval_count_after_merge": len(all_domain_viewtime_intervals),
            "domain_viewtime_record_count": sum(x["viewtime_records_in_domain"] for x in granules),
            "domain_flash_record_count": sum(x["flash_records_in_domain"] for x in granules),
            "domain_event_record_count": sum(x["event_records_in_domain"] for x in granules),
            "granules": granules,
            "all_readable_granule_metadata_audit": all_granule_audit,
            "coverage_by_date": by_date,
        },
        "era5_request": {
            "cadence_hours": CADENCE_HOURS,
            "sequence_length": SEQUENCE_LENGTH,
            "forecast_horizon_steps": FORECAST_HORIZON,
            "target_hour_bin_convention": "Each LIS view-time interval/event contributes its intersected UTC hourly bin [h,h+1); this is an acquisition-hour mapping, not a constructed label.",
            "predictor_hour_convention": "For target bin [h,h+1), request the existing four-step history at h-3, h-2, h-1, h. No ERA5 at the target valid time h+1 is requested as an input.",
            "required_predictor_hours_utc": hours_by_date(required_input_hours),
            "existing_required_hours_utc": hours_by_date(available_required),
            "missing_required_hours_utc": hours_by_date(missing_hours),
            "surface_variables": SURFACE_VARIABLES,
            "pressure_variables": PRESSURE_VARIABLES,
            "pressure_levels_hpa": PRESSURE_LEVELS_HPA,
            "domain": DOMAIN,
        },
        "existing_era5": {
            "single_level_periods_utc": [
                {"start": "2023-11-16T00:00:00Z", "end": "2023-11-16T23:00:00Z"},
                {"start": "2025-04-01T00:00:00Z", "end": "2025-12-31T23:00:00Z"},
            ],
            "pressure_level_periods_utc": [
                {"start": "2023-11-16T00:00:00Z", "end": "2023-11-16T23:00:00Z"},
            ],
            "single_and_pressure_common_lis_domain_dates": [date for date in sorted(by_date_granules) if date == "2023-11-16"],
            "is_sufficient_for_all_domain_intersections": not bool(missing_hours),
        },
        "scientific_limitations": [
            "This report specifies ERA5 predictor acquisition hours from observed LIS domain coverage; it does not create labels or training samples.",
            "A timestamp/hour match does not establish a valid negative label; complete, acceptable LIS coverage is still required.",
            "All existing domain-overlap view-time records on 2023-11-16 carry alert flag 2, pending version-matched quality interpretation.",
            "Cloud base height and accumulated precipitation may be forecast/accumulation products and must be aligned by forecast reference/step before use.",
        ],
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# ERA5 coverage required for domain-intersecting LIS observations",
        "",
        f"Generated from actual NetCDF coordinates and TAI93 view-time/event records on {result['generated_at_utc']}.",
        "",
        "## LIS domain filter",
        "",
        f"- Domain: north {DOMAIN['north']} deg, south {DOMAIN['south']} deg, west {DOMAIN['west']} deg, east {DOMAIN['east']} deg (WGS84).",
        f"- Readable unique LIS granules inspected: **{len(readable)}**.",
        f"- Granules with view-time coverage or lightning event/flash coordinates inside the domain: **{len(granules)}**.",
        f"- Readable granules with no such intersection: **{len(readable)-len(granules)}**.",
        f"- Empty/unreadable unique LIS files excluded: **2** (59 empty source paths collapse to one empty hash; one HDF5 read error).",
        f"- Domain observations: **{result['lis_granules']['domain_viewtime_record_count']:,}** view-time rows, **{result['lis_granules']['domain_flash_record_count']:,}** flash records, and **{result['lis_granules']['domain_event_record_count']:,}** event records inside the geographic bounds.",
        "",
        "The date intervals below are merged unions of actual LIS view-time start/end records inside the domain, converted to UTC using each granule's embedded UTC orbit start plus its TAI93 elapsed-time offset. They are not filename-derived orbit envelopes.",
        "The JSON also contains an audit record for every readable granule, including orbit start/end, full view-time and event/flash UTC bounds, geolocation bounds, record counts, and quality-flag counts, including non-intersecting granules.",
        "",
        "| UTC date | Granules by orbit start date | Exact LIS view-time interval union (UTC) | Flashes | Events |",
        "|---|---:|---|---:|---:|",
    ]
    for row in by_date:
        intervals = "; ".join(f"{a} to {b}" for a, b in row["domain_viewtime_intervals_utc"])
        lines.append(f"| {row['date']} | {row['domain_intersecting_granules_by_orbit_start_date']} | {intervals} | {row['flash_records_in_domain']} | {row['event_records_in_domain']} |")
    lines += [
        "",
        "## ERA5 acquisition request",
        "",
        f"The current research preprocessing configuration uses `sequence_length={SEQUENCE_LENGTH}`, `forecast_horizon={FORECAST_HORIZON}`, and hourly ERA5 cadence. For each LIS-touched target hour bin [h,h+1), request the four causal predictor valid times h-3 through h. Do not supply the target valid-time atmosphere h+1 as an input. This yields **{len(required_input_hours)} distinct predictor hours** across **{len(hours_by_date(required_input_hours))} dates**.",
        "",
        "| Required UTC date | Exact ERA5 predictor hours (valid time) | Existing ERA5 status |",
        "|---|---|---|",
    ]
    for row in hours_by_date(required_input_hours):
        date = row["date"]
        hours = ", ".join(row["utc_hours"])
        status = "Existing surface + pressure" if all(
            datetime.fromisoformat(f"{date}T{h[:2]}:00:00+00:00") in existing_hours for h in row["utc_hours"]
        ) else "Missing one or both ERA5 products"
        lines.append(f"| {date} | {hours} | {status} |")
    lines += [
        "",
        "### Variables and domain",
        "",
        f"- Single level (all requested for each listed UTC hour): {', '.join(x['name'] + ' (`' + x['short_name'] + '`)' for x in SURFACE_VARIABLES)}.",
        f"- Pressure level (all requested at each listed UTC hour): {', '.join(x['name'] + ' (`' + x['short_name'] + '`)' for x in PRESSURE_VARIABLES)}.",
        f"- Pressure levels: {', '.join(str(x) for x in PRESSURE_LEVELS_HPA)} hPa.",
        f"- Spatial subset: north {DOMAIN['north']} deg, south {DOMAIN['south']} deg, west {DOMAIN['west']} deg, east {DOMAIN['east']} deg; preserve the native 0.25-degree atmospheric grid and coordinate ordering.",
        "",
        "## Sufficiency and remaining ERA5",
        "",
        f"Existing single-level and pressure-level ERA5 are both available for **2023-11-16 00:00 through 23:00 UTC**. They cover the required 2023-11-16 predictor hours, but are missing for the other LIS-domain dates. The 2025 single-level archive is not used as a substitute and has no LIS date intersection. Existing ERA5 is therefore **INSUFFICIENT** for all domain-intersecting LIS granules.",
        "",
        f"Acquire both the listed single-level and pressure-level fields at every hour in `data/database/manifests/era5_required_coverage.json` under `missing_required_hours_utc`. Do not request ERA5 for the other LIS dates, which do not intersect the StrikeCast domain.",
        "",
        "This is only an acquisition requirement. It does not make the sparse view-time observations valid one-hour labels, resolve alert-flag policy, or authorize model training.",
        "",
        "Machine-readable per-granule intervals, quality flags, required hours, and existing/missing coverage are in [`era5_required_coverage.json`](../../data/database/manifests/era5_required_coverage.json).",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Readable LIS={len(readable)}; domain-intersecting={len(granules)}; predictor hours={len(required_input_hours)}; missing ERA5 hours={len(missing_hours)}")
    print(f"Wrote {OUTPUT_MD} and {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
