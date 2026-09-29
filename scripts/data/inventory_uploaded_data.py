#!/usr/bin/env python
"""Inventory copied ERA5 GRIB archives and ISS-LIS NetCDF files.

This script is metadata-only: it never constructs lightning labels, resamples
data, or changes source files. It requires optional dependencies from
requirements-data.txt and extracted GRIB members under data/interim.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _grib_inventory(path: Path) -> dict:
    try:
        from eccodes import codes_get, codes_grib_new_from_file, codes_release
    except ImportError as exc:
        raise RuntimeError("Install optional GRIB reader: pip install -r requirements-data.txt") from exc
    fields, grids, editions, producers = Counter(), Counter(), Counter(), Counter()
    forecast_references, forecast_steps = Counter(), Counter()
    validity = []

    def get(handle, key):
        try:
            return codes_get(handle, key)
        except Exception:
            return None

    with path.open("rb") as stream:
        while (handle := codes_grib_new_from_file(stream)) is not None:
            edition = get(handle, "edition")
            editions[str(edition)] += 1
            producers[(get(handle, "centre"), get(handle, "centreDescription"), get(handle, "class"),
                       get(handle, "expver"), get(handle, "stream"), get(handle, "type"))] += 1
            short_name = get(handle, "shortName")
            message_type, step_type = get(handle, "type"), get(handle, "stepType")
            fields[(short_name, get(handle, "name"), get(handle, "units"),
                    get(handle, "typeOfLevel"), get(handle, "level"), step_type, message_type)] += 1
            if message_type == "fc":
                reference = (short_name, get(handle, "dataDate"), get(handle, "dataTime"), step_type)
                forecast_references[reference] += 1
                forecast_steps[(short_name, get(handle, "stepRange"))] += 1
            date, time = get(handle, "validityDate"), get(handle, "validityTime")
            if date is not None and time is not None:
                validity.append(datetime.strptime(f"{date:08d}{time:04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc))
            grids[(get(handle, "gridType"), get(handle, "Ni"), get(handle, "Nj"),
                   get(handle, "latitudeOfFirstGridPointInDegrees"), get(handle, "latitudeOfLastGridPointInDegrees"),
                   get(handle, "longitudeOfFirstGridPointInDegrees"), get(handle, "longitudeOfLastGridPointInDegrees"),
                   get(handle, "iDirectionIncrementInDegrees"), get(handle, "jDirectionIncrementInDegrees"))] += 1
            codes_release(handle)
    return {
        "message_count": sum(editions.values()), "editions": dict(editions),
        "producer_identifiers": [
            {"centre": row[0], "centre_description": row[1], "class": row[2], "expver": row[3],
             "stream": row[4], "type": row[5], "message_count": count}
            for row, count in sorted(producers.items(), key=lambda item: str(item[0]))
        ],
        "valid_time_start_utc": min(validity).isoformat() if validity else None,
        "valid_time_end_utc": max(validity).isoformat() if validity else None,
        "field_signatures": [
            {"short_name": r[0], "name": r[1], "units": r[2], "level_type": r[3], "level": r[4],
             "step_type": r[5], "message_type": r[6], "message_count": count}
            for r, count in sorted(fields.items(), key=lambda item: str(item[0]))
        ],
        "forecast_reference_cycles": [
            {"short_name": r[0], "reference_date": r[1], "reference_time": r[2],
             "step_type": r[3], "message_count": count}
            for r, count in sorted(forecast_references.items(), key=lambda item: str(item[0]))
        ],
        "forecast_step_ranges": [
            {"short_name": r[0], "step_range": r[1], "message_count": count}
            for r, count in sorted(forecast_steps.items(), key=lambda item: str(item[0]))
        ],
        "grid_signatures": [
            {"grid_type": r[0], "ni": r[1], "nj": r[2], "first_lat": r[3], "last_lat": r[4],
             "first_lon": r[5], "last_lon": r[6], "i_increment_deg": r[7], "j_increment_deg": r[8],
             "message_count": count}
            for r, count in sorted(grids.items(), key=lambda item: str(item[0]))
        ],
    }


def _netcdf_inventory(path: Path, era5_bounds: tuple[float, float, float, float] | None) -> dict:
    try:
        import numpy as np
        from netCDF4 import Dataset
    except ImportError as exc:
        raise RuntimeError("Install optional NetCDF reader: pip install -r requirements-data.txt") from exc
    with Dataset(path, "r") as ds:
        variables = []
        for name, var in ds.variables.items():
            variables.append({"name": name, "dimensions": list(var.dimensions), "shape": list(var.shape),
                              "dtype": str(var.dtype),
                              "attributes": {a: str(getattr(var, a)) for a in var.ncattrs()}})

        def scalar(name):
            val = ds.variables[name][...]
            return val.item() if hasattr(val, "item") else val

        lat = np.asarray(ds.variables["viewtime_lat"][:], dtype=float)
        lon = np.asarray(ds.variables["viewtime_lon"][:], dtype=float)
        starts = np.asarray(ds.variables["viewtime_TAI93_start"][:], dtype=float)
        ends = np.asarray(ds.variables["viewtime_TAI93_end"][:], dtype=float)
        effective = np.asarray(ds.variables["viewtime_effective_obs"][:], dtype=float)
        alert = np.asarray(ds.variables["viewtime_alert_flag"][:], dtype=int)
        # Some valid LIS granules omit the flash/event record arrays when those
        # tables are empty. Preserve that absence; summary counts and view-time
        # coverage remain separately available.
        flash_lat = np.asarray(ds.variables["lightning_flash_lat"][:], dtype=float) if "lightning_flash_lat" in ds.variables else np.asarray([], dtype=float)
        flash_lon = np.asarray(ds.variables["lightning_flash_lon"][:], dtype=float) if "lightning_flash_lon" in ds.variables else np.asarray([], dtype=float)
        flash_alert = np.asarray(ds.variables["lightning_flash_alert_flag"][:], dtype=int) if "lightning_flash_alert_flag" in ds.variables else np.asarray([], dtype=int)
        event_alert = np.asarray(ds.variables["lightning_event_alert_flag"][:], dtype=int) if "lightning_event_alert_flag" in ds.variables else np.asarray([], dtype=int)
        roi_summary = None
        if era5_bounds:
            lat_min, lat_max, lon_min, lon_max = era5_bounds
            roi = (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)
            flash_roi = ((flash_lat >= lat_min) & (flash_lat <= lat_max)
                         & (flash_lon >= lon_min) & (flash_lon <= lon_max))
            n_lat = round((lat_max-lat_min)/0.5 + 1)
            n_lon = round((lon_max-lon_min)/0.5 + 1)
            roi_summary = {
                "bounds_wgs84": {"lat": [lat_min, lat_max], "lon": [lon_min, lon_max]},
                "nominal_half_degree_cell_centers": int(n_lat*n_lon),
                "viewtime_rows": int(roi.sum()),
                "unique_viewtime_cells": len(set(zip(lat[roi].tolist(), lon[roi].tolist()))),
                "effective_observation_seconds_cell_sum": float(effective[roi].sum()),
                "viewtime_alert_flag_counts": {str(k): int(v) for k, v in Counter(alert[roi]).items()},
                "flash_count": int(flash_roi.sum()),
                "flash_alert_flag_counts": {str(k): int(v) for k, v in Counter(flash_alert[flash_roi]).items()},
                "viewtime_tai93_start_range": [float(starts[roi].min()), float(starts[roi].max())] if roi.any() else None,
                "viewtime_tai93_end_range": [float(ends[roi].min()), float(ends[roi].max())] if roi.any() else None,
            }

        orbit_start_tai = float(scalar("orbit_summary_TAI93_start"))
        orbit_end_tai = float(scalar("orbit_summary_TAI93_end"))
        orbit_start = datetime.fromisoformat(str(scalar("orbit_summary_UTC_start")).replace("Z", "+00:00"))
        orbit_end = orbit_start + timedelta(seconds=orbit_end_tai-orbit_start_tai)
        return {
            "format": "NetCDF-4/HDF5",
            "global_attributes": {n: str(getattr(ds, n)) for n in ds.ncattrs()},
            "dimensions": {n: len(dim) for n, dim in ds.dimensions.items()},
            "variables": variables,
            "orbit_id": int(scalar("orbit_summary_id_number")),
            "orbit_start_utc": orbit_start.isoformat(),
            "orbit_end_utc_derived_from_TAI93_duration": orbit_end.isoformat(),
            "orbit_start_longitude_deg": float(scalar("orbit_summary_start_longitude")),
            "orbit_end_longitude_deg": float(scalar("orbit_summary_end_longitude")),
            "flash_count": int(scalar("point_summary_flash_count")),
            "group_count": int(scalar("point_summary_group_count")),
            "event_count": int(scalar("point_summary_event_count")),
            "viewtime_count": int(scalar("point_summary_vt_count")),
            "viewtime_bounds": {"lat": [float(lat.min()), float(lat.max())], "lon": [float(lon.min()), float(lon.max())]},
            "viewtime_spacing_deg": 0.5,
            "viewtime_alert_flag_counts": {str(k): int(v) for k, v in Counter(alert).items()},
            "event_alert_flag_counts": {str(k): int(v) for k, v in Counter(event_alert).items()},
            "era5_spatial_overlap": roi_summary,
        }


def build_inventory(raw_root: Path, interim_root: Path) -> dict:
    try:
        from netCDF4 import Dataset  # noqa: F401
        from eccodes import codes_grib_new_from_file  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Install optional readers with: pip install -r requirements-data.txt") from exc
    grib_files = {p.stem: p for p in interim_root.rglob("*.grib")}
    previous_manifest_path = ROOT / "data" / "database" / "manifests" / "dataset_inventory.json"
    previous_archives = {}
    if previous_manifest_path.is_file():
        try:
            previous = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
            previous_archives = {
                item["sha256"]: item for item in previous.get("files", [])
                if item.get("format") == "ZIP archive containing GRIB" and item.get("sha256")
            }
        except (OSError, ValueError, KeyError, TypeError):
            previous_archives = {}
    archives = []
    for archive in sorted(raw_root.rglob("*.zip")):
        archive_hash = sha256(archive)
        cached = previous_archives.get(archive_hash)
        if cached:
            crc_status, members, grib_data = cached["zip_crc_check"], cached["members"], cached["grib"]
        else:
            with zipfile.ZipFile(archive) as z:
                bad = z.testzip()
                members = [{"name": i.filename, "compressed_bytes": i.compress_size,
                            "uncompressed_bytes": i.file_size, "compression_method": i.compress_type}
                           for i in z.infolist()]
            crc_status = "PASS" if bad is None else f"FAIL: {bad}"
            grib_path = grib_files.get(archive.stem)
            if grib_path is None:
                raise RuntimeError(f"Extracted GRIB member missing for {archive.name} under {interim_root}")
            grib_data = _grib_inventory(grib_path)
        category = archive.parent.name
        archives.append({"file": archive.name, "category": category,
                         "relative_path": archive.relative_to(raw_root).as_posix(),
                         "format": "ZIP archive containing GRIB", "size_bytes": archive.stat().st_size,
                         "sha256": archive_hash, "zip_crc_check": crc_status,
                         "members": members, "grib": grib_data})

    grids = [g for a in archives for g in a["grib"]["grid_signatures"] if g["grid_type"] == "regular_ll"]
    bounds = None
    if grids:
        bounds = (min(min(g["first_lat"], g["last_lat"]) for g in grids),
                  max(max(g["first_lat"], g["last_lat"]) for g in grids),
                  min(min(g["first_lon"], g["last_lon"]) for g in grids),
                  max(max(g["first_lon"], g["last_lon"]) for g in grids))
    ncfiles, seen_hashes = [], set()
    for path in sorted(raw_root.rglob("*.nc")):
        digest = sha256(path)
        item = {"file": path.name, "category": path.parent.name,
                "relative_path": path.relative_to(raw_root).as_posix(),
                "format": "NetCDF-4/HDF5", "size_bytes": path.stat().st_size,
                "sha256": digest, "duplicate_content": digest in seen_hashes}
        if digest not in seen_hashes:
            if path.stat().st_size == 0:
                item["format"] = "empty file (invalid NetCDF)"
                item["netcdf_read_error"] = "zero-byte file; no NetCDF content"
            else:
                try:
                    item["netcdf"] = _netcdf_inventory(path, bounds)
                except Exception as exc:
                    item["netcdf_read_error"] = f"{type(exc).__name__}: {exc}"
            seen_hashes.add(digest)
        ncfiles.append(item)
    # Record exact source-file mirrors at the repository root without counting
    # them as additional datasets. This catches manually staged archives while
    # keeping data/raw as the canonical immutable inventory root.
    canonical_by_name = {row["file"]: row["sha256"] for row in archives + ncfiles}
    workspace_copies = []
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and path.name in canonical_by_name:
            digest = sha256(path)
            if digest == canonical_by_name[path.name]:
                workspace_copies.append({
                    "file": path.name,
                    "relative_path": path.relative_to(ROOT).as_posix(),
                    "sha256": digest,
                    "identical_to_raw_source": True,
                    "counted_as_additional_dataset": False,
                })
    ingestion_manifest = ROOT / "data" / "database" / "manifests" / "historical_lis_ingestion.json"
    ingestion_summary = None
    if ingestion_manifest.is_file():
        try:
            source = json.loads(ingestion_manifest.read_text(encoding="utf-8"))
            ingestion_summary = {
                key: source.get(key) for key in (
                    "source_root", "source_file_count", "netcdf_file_count",
                    "nonempty_netcdf_file_count", "empty_file_count",
                    "unique_netcdf_content_count", "unique_nonempty_netcdf_content_count",
                    "duplicate_netcdf_file_count", "new_raw_copy_count",
                    "new_nonempty_raw_copy_count", "existing_raw_content_matches",
                    "parseable_unique_netcdf_count", "failed_unique_netcdf_count",
                    "parseable_source_file_count", "invalid_empty_source_file_count",
                    "invalid_or_unreadable_source_file_count", "source_collections",
                )
            }
        except (OSError, ValueError, TypeError):
            ingestion_summary = {"error": "Could not read historical LIS ingestion provenance manifest"}
    return {
        "inventory_schema_version": "1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inventory_method": "SHA-256, ZIP CRC, ecCodes GRIB metadata, and netCDF4 variable/coordinate metadata; raw sources read only",
        "raw_root": (raw_root.relative_to(ROOT).as_posix() if ROOT in raw_root.parents else raw_root.name),
        "files": archives + ncfiles,
        "workspace_duplicate_copies": workspace_copies,
        "ingestion_provenance_manifest": (
            ingestion_manifest.relative_to(ROOT).as_posix() if ingestion_manifest.is_file() else None
        ),
        "external_ingestion_summary": ingestion_summary,
        "notes": [
            "File names and embedded globals do not fully establish provider delivery provenance or licensing; acquisition records require review.",
            "ERA5 validity bounds are metadata coverage; LIS orbit coverage is sparse, not continuous.",
            "Rectangular common bounds do not prove per-cell temporal observation coverage.",
            "This inventory creates no labels, paired dataset, model metrics, or acceptance status.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--interim-root", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--output", type=Path, default=ROOT / "data/database/manifests/dataset_inventory.json")
    args = parser.parse_args()
    try:
        result = build_inventory(args.raw_root.resolve(), args.interim_root.resolve())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Inventoried {len(result['files'])} raw files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
