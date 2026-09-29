"""
M2 entry point for reading M1's validated output (Phase 2 / Phase 3).

Per docs/m1_m2_contract.md, the manifest at
data/<sample_demo|raw>/metadata/manifest.json is the recommended,
non-hard-coded way to discover the current M1 output files (filenames
embed timestamps and must not be guessed). This module is the only place
in M2 that touches src.ingestion — everything downstream works against
plain DataRecord objects.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.contract import DataRecord, QualityStatus
from src.ingestion.storage import load_record

from .config import PreprocessingConfig


class M1RecordUnavailableError(RuntimeError):
    """Raised when a required M1 source is missing or excluded (e.g. a
    'failed'-quality record with exclude_failed_records enabled), so the
    caller gets an explicit error rather than a silently incomplete
    feature set."""


def _manifest_path(config: PreprocessingConfig, demo: bool) -> Path:
    base = config.sample_demo_dir if demo else config.raw_dir.parent / "raw"
    return base / "metadata" / "manifest.json"


def load_manifest(config: PreprocessingConfig, demo: bool = True) -> dict:
    manifest_path = _manifest_path(config, demo)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"M1 manifest not found at {manifest_path}. Run "
            "`python -m src.ingestion.demo_generator` first (demo mode), "
            "or point PreprocessingConfig at a run with real M1 output."
        )
    with open(manifest_path, "r") as f:
        return json.load(f)


def load_all_records(
    config: PreprocessingConfig, demo: bool = True
) -> dict[str, DataRecord]:
    """Load one DataRecord per M1 source (satellite, lightning, nwp,
    radar), following the manifest. Records with quality_status ==
    'failed' are excluded when missing_data.exclude_failed_records is
    true (the default) — per docs/m1_m2_contract.md: 'M2 should not
    consume a failed record without explicit handling.'"""
    manifest = load_manifest(config, demo=demo)
    exclude_failed = config.missing_data_cfg().get("exclude_failed_records", True)

    records: dict[str, DataRecord] = {}
    excluded: dict[str, str] = {}
    for name, info in manifest["sources"].items():
        npz_path = config.data_root / info["npz_path"]
        json_path = config.data_root / info["json_path"]
        record = load_record(npz_path, json_path)
        if (
            exclude_failed
            and record.quality is not None
            and record.quality.quality_status == QualityStatus.FAILED
        ):
            excluded[name] = record.quality.quality_status.value
            continue
        records[name] = record

    if excluded:
        # Not fatal by itself (a single degraded/failed source shouldn't
        # necessarily kill the whole run in a larger deployment), but the
        # MVP feature set assumes all four sources are present, so make
        # the gap loud rather than silently proceeding with fewer
        # channels than the documented schema promises.
        raise M1RecordUnavailableError(
            f"The following M1 sources were excluded for quality_status="
            f"'failed' and exclude_failed_records=true: {excluded}. "
            "Re-run M1 ingestion, or set missing_data.exclude_failed_records "
            "to false to proceed with degraded data (not recommended)."
        )

    return records
