#!/usr/bin/env python
"""Inspect current ERA5 GRIB files against LIS-derived required timestamps.

ZIP members are streamed to temporary files only after path, symlink, size,
expansion and compression-ratio checks. Archive paths are never extracted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
SOURCE_COVERAGE = ROOT / "data/database/manifests/era5_required_coverage.json"
OUTPUT = ROOT / "data/manifests/era5_required_coverage.json"
REPORT = ROOT / "artifacts/reports/ERA5_COVERAGE_STATUS.md"
MAX_ARCHIVE_BYTES = 8 * 1024**3
MAX_EXPANDED_BYTES = 20 * 1024**3
MAX_MEMBER_BYTES = 8 * 1024**3
MAX_RATIO = 1000
CHUNK_SIZE = 1024 * 1024


class PlannerEnvironmentError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_zip_info(info: zipfile.ZipInfo, total_expanded: int) -> int:
    name = info.filename
    pure = PurePosixPath(name)
    mode = (info.external_attr >> 16) & 0o170000
    if (not name or "\\" in name or pure.is_absolute() or re.match(r"^[A-Za-z]:", name)
            or ".." in pure.parts or mode == 0o120000):
        raise ValueError(f"unsafe archive member path or symlink: {name!r}")
    if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"archive member exceeds size limit: {name!r}")
    if info.file_size > MAX_RATIO * max(info.compress_size, 1):
        raise ValueError(f"archive member exceeds expansion ratio limit: {name!r}")
    total_expanded += info.file_size
    if total_expanded > MAX_EXPANDED_BYTES:
        raise ValueError("archive total expanded size exceeds configured limit")
    return total_expanded


def read_member_to_temp(archive: zipfile.ZipFile, info: zipfile.ZipInfo, directory: Path) -> Path:
    destination = directory / "member.grib"
    actual = 0
    with archive.open(info, "r") as source, destination.open("xb") as target:
        while block := source.read(CHUNK_SIZE):
            actual += len(block)
            if actual > info.file_size or actual > MAX_MEMBER_BYTES:
                raise ValueError(f"archive member expanded beyond declared/configured size: {info.filename!r}")
            target.write(block)
    if actual != info.file_size:
        raise ValueError(f"archive member size mismatch: {info.filename!r}")
    return destination


def scan_grib(path: Path, product: str) -> tuple[set[tuple[datetime, str, int | None]], int]:
    try:
        from eccodes import codes_get, codes_grib_new_from_file, codes_release
    except ImportError as exc:
        raise PlannerEnvironmentError("ecCodes is required; install requirements-data.txt") from exc
    records: set[tuple[datetime, str, int | None]] = set()
    count = 0
    with path.open("rb") as stream:
        while True:
            handle = codes_grib_new_from_file(stream)
            if handle is None:
                break
            try:
                short_name = str(codes_get(handle, "shortName"))
                date = int(codes_get(handle, "validityDate"))
                hhmm = int(codes_get(handle, "validityTime"))
                valid = datetime.strptime(f"{date:08d}{hhmm:04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                level_type = str(codes_get(handle, "typeOfLevel"))
                level = int(codes_get(handle, "level")) if level_type == "isobaricInhPa" else None
                records.add((valid, short_name, level))
                count += 1
            finally:
                codes_release(handle)
    if not count:
        raise ValueError("no GRIB messages found")
    return records, count


def product_from_category(category: str) -> str:
    key = category.lower()
    if "pressure" in key or "pl" in key:
        return "pressure_levels"
    if key == "era5" or "single" in key or "sl" in key:
        return "single_levels"
    raise ValueError(f"cannot classify ERA5 product directory {category!r}")


def inspect_archive(path: Path) -> tuple[str, str, set[tuple[datetime, str, int | None]], int]:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds configured compressed-size limit")
    digest = sha256_file(path)
    product = product_from_category(path.parent.name)
    records: set[tuple[datetime, str, int | None]] = set()
    message_count = 0
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if not infos:
            raise ValueError("empty ZIP archive")
        expanded = 0
        for info in infos:
            expanded = validate_zip_info(info, expanded)
        grib_infos = [item for item in infos if not item.is_dir() and
                      item.filename.lower().endswith((".grib", ".grb", ".grib2", ".grb2"))]
        if len(grib_infos) != 1:
            raise ValueError("archive must contain exactly one GRIB member")
        # Reading every member enforces CRC checks while observing expansion limits.
        for info in infos:
            if info.is_dir():
                continue
            if info is grib_infos[0]:
                with tempfile.TemporaryDirectory(prefix="strikecast-era5-") as temp:
                    grib_path = read_member_to_temp(archive, info, Path(temp))
                    records, message_count = scan_grib(grib_path, product)
            else:
                read_count = 0
                with archive.open(info, "r") as stream:
                    while block := stream.read(CHUNK_SIZE):
                        read_count += len(block)
                        if read_count > info.file_size:
                            raise ValueError(f"member size mismatch: {info.filename!r}")
                if read_count != info.file_size:
                    raise ValueError(f"member size mismatch: {info.filename!r}")
    return digest, product, records, message_count


def grouped_hours(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(rows, key=lambda item: (item["timestamp_utc"], item.get("product", ""))):
        timestamp = datetime.fromisoformat(row["timestamp_utc"])
        grouped[timestamp.date().isoformat()].append({k: v for k, v in row.items() if k != "timestamp_utc"} | {"utc_hour": timestamp.strftime("%H:00")})
    return [{"date": date, "hours": entries} for date, entries in sorted(grouped.items())]


def main() -> int:
    try:
        source = json.loads(SOURCE_COVERAGE.read_text(encoding="utf-8"))
        request = source["era5_request"]
        lis = source["lis_granules"]
        required = {
            datetime.fromisoformat(f"{row['date']}T{hour}:00:00+00:00")
            for row in request["required_predictor_hours_utc"] for hour in row["utc_hours"]
        }
        sl_names = {str(field["short_name"]) for field in request["surface_variables"]}
        pl_names = {str(field["short_name"]) for field in request["pressure_variables"]}
        levels = {int(value) for value in request["pressure_levels_hpa"]}
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise PlannerEnvironmentError(f"LIS-derived ERA5 requirement manifest is invalid: {exc}") from exc
    if not required or not sl_names or not pl_names or not levels:
        raise PlannerEnvironmentError("LIS-derived ERA5 requirement manifest has empty requirements")

    records_by_product: dict[str, set[tuple[datetime, str, int | None]]] = {
        "single_levels": set(), "pressure_levels": set()
    }
    files, invalid = [], []
    seen_hashes: set[str] = set()
    # Only atmospheric products are relevant here. LIS archives are audited by
    # the LIS inventory pipeline and can be orders of magnitude larger.
    era5_archives = [p for p in RAW.rglob("*.zip")
                     if any("era5" in part.lower() for part in p.relative_to(RAW).parts[:-1])]
    for archive_path in sorted(era5_archives):
        try:
            digest, product, records, messages = inspect_archive(archive_path)
            duplicate = digest in seen_hashes
            seen_hashes.add(digest)
            if not duplicate:
                records_by_product[product].update(records)
            files.append({"path": archive_path.relative_to(ROOT).as_posix(), "sha256": digest,
                          "product": product, "message_count": messages, "duplicate_content": duplicate,
                          "status": "VALID"})
        except PlannerEnvironmentError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            invalid.append({"path": archive_path.relative_to(ROOT).as_posix(), "status": "INVALID", "reason": str(exc)})

    # Also inspect standalone GRIB files that have not been archived.
    era5_gribs = [p for pattern in ("*.grib", "*.grb") for p in RAW.rglob(pattern)
                  if any("era5" in part.lower() for part in p.relative_to(RAW).parts[:-1])]
    for grib_path in sorted(era5_gribs):
        digest = sha256_file(grib_path)
        if digest in seen_hashes:
            continue
        try:
            product = product_from_category(grib_path.parent.name)
            records, messages = scan_grib(grib_path, product)
            records_by_product[product].update(records)
            seen_hashes.add(digest)
            files.append({"path": grib_path.relative_to(ROOT).as_posix(), "sha256": digest,
                          "product": product, "message_count": messages, "duplicate_content": False,
                          "status": "VALID"})
        except PlannerEnvironmentError:
            raise
        except (OSError, ValueError) as exc:
            invalid.append({"path": grib_path.relative_to(ROOT).as_posix(), "status": "INVALID", "reason": str(exc)})

    def field_sets(product: str, hour: datetime) -> set[str]:
        return {short for valid_time, short, _ in records_by_product[product] if valid_time == hour}

    required_rows, available_rows, missing_rows = [], [], []
    for hour in sorted(required):
        sl_fields = field_sets("single_levels", hour)
        pl_fields = {(short, level) for valid_time, short, level in records_by_product["pressure_levels"]
                     if valid_time == hour and level in levels}
        missing_sl = sorted(sl_names - sl_fields)
        missing_pl = sorted(f"{name}@{level}hPa" for level in sorted(levels) for name in sorted(pl_names)
                            if (name, level) not in pl_fields)
        row = {"timestamp_utc": hour.isoformat(), "single_levels_complete": not missing_sl,
               "pressure_levels_complete": not missing_pl, "missing_single_level_fields": missing_sl,
               "missing_pressure_level_fields": missing_pl,
               "status": "AVAILABLE" if not missing_sl and not missing_pl else "MISSING"}
        required_rows.append(row)
        (available_rows if row["status"] == "AVAILABLE" else missing_rows).append(row)

    extra_rows = []
    for product, product_records in records_by_product.items():
        times = {valid for valid, _, _ in product_records}
        for hour in sorted(times - required):
            extra_rows.append({"timestamp_utc": hour.isoformat(), "product": product,
                               "field_count": sum(1 for valid, _, _ in product_records if valid == hour)})

    generated = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "strikecast-era5-coverage-plan-v1",
        "generated_at_utc": generated,
        "status": "COMPLETE" if not missing_rows and not invalid else "INCOMPLETE",
        "coverage_status": "READY_FOR_PAIRING" if not missing_rows and not invalid else "BLOCKED_MISSING_OR_INVALID_ERA5",
        "source_lis_coverage_manifest": SOURCE_COVERAGE.relative_to(ROOT).as_posix(),
        "source_lis_manifest_generated_at_utc": source.get("generated_at_utc"),
        "domain": source.get("domain"),
        "lis_granules": {key: lis.get(key) for key in (
            "readable_unique_granules_inspected", "domain_intersecting_granules",
            "non_intersecting_readable_granules", "domain_dates_utc")},
        "requirements": {"required_hour_count": len(required), "single_level_short_names": sorted(sl_names),
                         "pressure_level_short_names": sorted(pl_names), "pressure_levels_hpa": sorted(levels),
                         "required_hours": grouped_hours(required_rows)},
        "available": grouped_hours(available_rows), "available_hour_count": len(available_rows),
        "missing": grouped_hours(missing_rows), "missing_hour_count": len(missing_rows),
        "missing_hours_utc": [row["timestamp_utc"] for row in missing_rows],
        "available_hours_utc": [row["timestamp_utc"] for row in available_rows],
        "required_hours_utc": [row["timestamp_utc"] for row in required_rows],
        "invalid": invalid, "valid_file_count": len(files), "files": files,
        "extra": grouped_hours(extra_rows), "extra_hour_product_count": len(extra_rows),
        "limitations": [
            "Coverage requires every requested short name and pressure level at the exact valid hour; this planner does not verify operational issue-time availability.",
            "The LIS granule coverage manifest must be regenerated from current raw NetCDF inputs when the LIS collection changes.",
            "A complete ERA5 hour is necessary but not sufficient for a valid lightning training label.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(report), encoding="utf-8")
    print(json.dumps({"status": "COMPLETE" if not missing_rows and not invalid else "INCOMPLETE", "coverage_status": report["status"], "required": len(required), "available": len(available_rows),
                      "missing": len(missing_rows), "invalid_files": len(invalid), "extra_hour_products": len(extra_rows),
                      "manifest": OUTPUT.relative_to(ROOT).as_posix()}))
    return 0


def render_report(report: dict) -> str:
    def bullet_groups(groups: list[dict]) -> list[str]:
        lines = []
        for group in groups:
            hours = ", ".join(f"{row.get('utc_hour')}" + (f" ({row.get('product')})" if row.get("product") else "") for row in group["hours"])
            lines.append(f"- {group['date']}: {hours}")
        return lines or ["- None"]

    return "\n".join([
        "# ERA5 coverage status", "", f"Status: **{report['status']}**", "",
        f"Required: {report['requirements']['required_hour_count']} distinct UTC hours. Available complete hours: {report['available_hour_count']}. Missing or incomplete hours: {report['missing_hour_count']}.", "",
        "Domain: N20/S8/W72/E82. Availability is counted only when all required variables and pressure levels are present at that valid hour.", "",
        "## REQUIRED", "", *bullet_groups(report["requirements"]["required_hours"]), "",
        "## AVAILABLE", "", *bullet_groups(report["available"]), "",
        "## MISSING", "", *bullet_groups(report["missing"]), "",
        "## INVALID", "", *([f"- `{row['path']}`: {row['reason']}" for row in report["invalid"]] or ["- None"]), "",
        "## EXTRA", "", *bullet_groups(report["extra"]), "",
        "## Variables", "", f"Single levels: {', '.join(report['requirements']['single_level_short_names'])}.",
        f"Pressure levels: {', '.join(report['requirements']['pressure_level_short_names'])}; {', '.join(map(str, report['requirements']['pressure_levels_hpa']))} hPa.", "",
        "A complete ERA5 hour does not prove LIS observed the corresponding label interval. See the machine-readable manifest for exact per-file hashes and missing fields.", "",
    ])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlannerEnvironmentError as exc:
        print(json.dumps({"status": "ENVIRONMENT_FAILURE", "error": str(exc)}))
        raise SystemExit(3)
