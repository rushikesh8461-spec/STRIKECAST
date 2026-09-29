"""
Missing-data detection and QualityReport assembly (Phase 6).

Combines temporal, spatial, and schema validation results plus a
missing-fraction computation into the single QualityReport object that
travels with every DataRecord (contract.py).
"""

from __future__ import annotations

import numpy as np

from ..contract import QualityReport, QualityStatus, SchemaStatus, SourceType, utc_now_iso


def compute_missing_fraction(data: np.ndarray, sentinel: float | None = None) -> float:
    """Fraction of values that are NaN or equal to `sentinel` (a legacy
    fill value some raw formats may still use before ingestion normalizes
    it to NaN — see docs/m1_m2_contract.md 'missing value representation')."""
    if data.size == 0:
        return 1.0
    missing = np.isnan(data)
    if sentinel is not None:
        missing = missing | (data == sentinel)
    return float(np.sum(missing)) / float(data.size)


def compute_quality_report(
    source: SourceType,
    temporal_result: dict,
    spatial_result: dict,
    schema_result: dict | None,
    missing_fraction: float,
    degraded_missing_fraction: float,
    failed_missing_fraction: float,
    min_coverage_fraction: float,
) -> QualityReport:
    issues: list[str] = []
    issues.extend(temporal_result.get("issues", []))
    issues.extend(spatial_result.get("issues", []))
    if schema_result is not None:
        issues.extend(schema_result.get("issues", []))

    coverage_fraction = temporal_result.get("coverage_fraction", 1.0)

    if schema_result is None:
        schema_status = SchemaStatus.NOT_CHECKED
        valid_fraction = 1.0
    elif schema_result["valid"]:
        schema_status = SchemaStatus.VALID
        fractions = [v["valid_fraction"] for v in schema_result["per_variable"].values()]
        valid_fraction = float(np.mean(fractions)) if fractions else 0.0
    else:
        schema_status = SchemaStatus.INVALID
        fractions = [v["valid_fraction"] for v in schema_result["per_variable"].values()]
        valid_fraction = float(np.mean(fractions)) if fractions else 0.0

    # Overall status: worst-of temporal/spatial/schema validity + thresholds.
    hard_fail = (
        not temporal_result.get("valid", True) and temporal_result.get("n_duplicates") is None
    ) or (schema_result is not None and not spatial_result.get("valid", True))

    if (
        coverage_fraction < min_coverage_fraction
        or missing_fraction > failed_missing_fraction
        or (schema_result is not None and schema_status == SchemaStatus.INVALID and valid_fraction < 0.5)
    ):
        quality_status = QualityStatus.FAILED
    elif missing_fraction > degraded_missing_fraction or issues:
        quality_status = QualityStatus.DEGRADED
    else:
        quality_status = QualityStatus.OK

    ts_start = temporal_result.get("timestamp_start", "")
    ts_end = temporal_result.get("timestamp_end", "")

    return QualityReport(
        source=source,
        generated_at=utc_now_iso(),
        timestamp_range=(ts_start, ts_end),
        coverage_fraction=coverage_fraction,
        missing_fraction=missing_fraction,
        valid_fraction=valid_fraction,
        schema_status=schema_status,
        quality_status=quality_status,
        issues=issues,
    )
