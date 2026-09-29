#!/usr/bin/env python
"""Hash, de-duplicate, and copy the read-only historical LIS drop into data/raw.

The source tree is not modified. Exact byte duplicates are preserved in the
ingestion manifest, but only one canonical copy is stored in data/raw.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "NEW DATA"
RAW_LIGHTNING = ROOT / "data" / "raw" / "lightning"
OUTPUT = ROOT / "data" / "database" / "manifests" / "historical_lis_ingestion.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if not SOURCE.is_dir():
        raise SystemExit(f"Historical source directory not found: {SOURCE}")

    source_files = sorted(path for path in SOURCE.rglob("*") if path.is_file())
    netcdf_files = [path for path in source_files if path.suffix.lower() in {".nc", ".nc4"}]
    groups: dict[str, list[Path]] = defaultdict(list)
    records: dict[Path, dict] = {}
    for path in netcdf_files:
        digest = sha256(path)
        groups[digest].append(path)
        records[path] = {
            "source_relative_path": path.relative_to(SOURCE).as_posix(),
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": digest,
            "file_validation": "FAIL_EMPTY" if path.stat().st_size == 0 else "PENDING_NETCDF_OPEN",
        }

    existing_raw: dict[str, Path] = {}
    for path in sorted(RAW_LIGHTNING.rglob("*.nc")) + sorted(RAW_LIGHTNING.rglob("*.nc4")):
        existing_raw.setdefault(sha256(path), path)

    # Choose a representative from the fullest source collection to preserve
    # the most complete provenance path when duplicate copies exist.
    source_collection_counts: dict[str, int] = defaultdict(int)
    for path in netcdf_files:
        collection = path.relative_to(SOURCE).parts[0]
        source_collection_counts[collection] += 1
    collection_rank = sorted(source_collection_counts, key=lambda item: (-source_collection_counts[item], item))
    rank = {collection: index for index, collection in enumerate(collection_rank)}
    representatives = {
        digest: min(paths, key=lambda path: (rank[path.relative_to(SOURCE).parts[0]], path.as_posix()))
        for digest, paths in groups.items()
    }

    copied_by_hash: dict[str, Path] = {}
    for digest, representative in sorted(representatives.items(), key=lambda item: item[1].as_posix()):
        if digest in existing_raw:
            copied_by_hash[digest] = existing_raw[digest]
            continue
        relative = representative.relative_to(SOURCE)
        destination = RAW_LIGHTNING / "historical_lis" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256(destination) != digest:
                raise RuntimeError(f"Refusing to overwrite non-identical destination: {destination}")
        else:
            shutil.copy2(representative, destination)
        copied_by_hash[digest] = destination

    manifest_files = []
    for path in source_files:
        if path in records:
            record = records[path]
            digest = record["sha256"]
            same_hash_sources = sorted(
                (other for other in groups[digest] if other != path),
                key=lambda other: other.relative_to(SOURCE).as_posix(),
            )
            record.update({
                "format": ("empty file (invalid NetCDF)" if path.stat().st_size == 0 else
                           ("NetCDF" if path.suffix.lower() == ".nc" else "NetCDF-4/HDF5")),
                "duplicate_source_paths": [other.relative_to(SOURCE).as_posix() for other in same_hash_sources],
                "duplicate_of_existing_raw": digest in existing_raw,
                "canonical_raw_path": copied_by_hash[digest].relative_to(ROOT).as_posix(),
                "copied_to_raw": copied_by_hash[digest].is_relative_to(RAW_LIGHTNING / "historical_lis"),
            })
            manifest_files.append(record)
        else:
            manifest_files.append({
                "source_relative_path": path.relative_to(SOURCE).as_posix(),
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "format": "unsupported/unclassified",
                "sha256": sha256(path),
                "copied_to_raw": False,
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": SOURCE.relative_to(ROOT).as_posix(),
        "source_read_only": True,
        "source_file_count": len(source_files),
        "netcdf_file_count": len(netcdf_files),
        "nonempty_netcdf_file_count": sum(path.stat().st_size > 0 for path in netcdf_files),
        "empty_file_count": sum(path.stat().st_size == 0 for path in netcdf_files),
        "unique_netcdf_content_count": len(groups),
        "unique_nonempty_netcdf_content_count": sum(
            any(path.stat().st_size > 0 for path in paths) for paths in groups.values()
        ),
        "duplicate_netcdf_file_count": len(netcdf_files) - len(groups),
        "new_raw_copy_count": sum(path.is_relative_to(RAW_LIGHTNING / "historical_lis") for path in copied_by_hash.values()),
        "new_nonempty_raw_copy_count": sum(
            path.is_relative_to(RAW_LIGHTNING / "historical_lis") and path.stat().st_size > 0
            for path in copied_by_hash.values()
        ),
        "existing_raw_content_matches": sum(digest in existing_raw for digest in groups),
        "source_collections": [
            {"directory": collection, "file_count": count}
            for collection, count in sorted(source_collection_counts.items())
        ],
        "files": manifest_files,
        "notes": [
            "Source files were opened read-only and left unchanged.",
            "A content hash, not a filename, defines an exact duplicate.",
            "Existing raw matches and repeated source copies point to one canonical raw path and are not counted as new observations.",
        ],
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Scanned {len(source_files)} source files; {len(netcdf_files)} NetCDF, "
        f"{len(groups)} unique contents; copied {manifest['new_raw_copy_count']} new files; "
        f"manifest: {OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
