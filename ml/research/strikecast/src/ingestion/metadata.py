"""Metadata and provenance helpers (Phase 6 / contract requirement)."""

from __future__ import annotations

from .contract import DataRecord, utc_now_iso


def build_provenance(
    source_id: str,
    dataset_version: str,
    acquisition_method: str,
    is_synthetic: bool,
    notes: str = "",
) -> dict:
    """
    Standard provenance dict attached to every DataRecord.

    is_synthetic=True must be set for any mocked/generated demo data — M2
    (and downstream consumers) must never mistake synthetic data for a real
    observation.
    """
    return {
        "source_id": source_id,
        "dataset_version": dataset_version,
        "acquisition_method": acquisition_method,
        "is_synthetic": is_synthetic,
        "ingested_at": utc_now_iso(),
        "notes": notes,
    }


def write_metadata_sidecar(record: DataRecord, path) -> None:
    """Write the metadata-only (no bulk array) JSON sidecar for a DataRecord."""
    import json

    with open(path, "w") as f:
        json.dump(record.as_metadata_dict(), f, indent=2, default=str)
