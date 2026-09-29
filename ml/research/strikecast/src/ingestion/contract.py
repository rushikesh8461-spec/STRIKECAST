"""
The M1 -> M2 Data Contract.

Every data source adapter in this package (satellite, lightning, NWP, radar)
produces output conforming to the types defined here. This is the ONLY
interface M2 should rely on. Internal adapter implementation details may
change without breaking M2, as long as this contract is honored.

See docs/m1_m2_contract.md for the full narrative specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import numpy as np


class SourceType(str, Enum):
    """The four conceptual multimodal data sources M1 is responsible for."""

    SATELLITE = "satellite"
    LIGHTNING = "lightning"
    NWP = "nwp"
    RADAR = "radar"


class QualityStatus(str, Enum):
    """Overall quality verdict attached to every DataRecord."""

    OK = "ok"
    DEGRADED = "degraded"   # usable, but missing_fraction above warning threshold
    FAILED = "failed"       # unusable — schema/temporal/spatial validation failed


class SchemaStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    NOT_CHECKED = "not_checked"


@dataclass
class GridSpec:
    """
    Spatial grid specification. Every DataRecord's `data` array (when gridded)
    is indexed as data[time, lat, lon, ...] and its coordinates are given by
    lat_values / lon_values below, in degrees, WGS84.
    """

    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    lat_resolution_deg: float
    lon_resolution_deg: float
    n_lat: int
    n_lon: int
    lat_values: np.ndarray  # shape (n_lat,)
    lon_values: np.ndarray  # shape (n_lon,)

    def as_metadata_dict(self) -> dict:
        return {
            "lat_min": self.lat_min,
            "lat_max": self.lat_max,
            "lon_min": self.lon_min,
            "lon_max": self.lon_max,
            "lat_resolution_deg": self.lat_resolution_deg,
            "lon_resolution_deg": self.lon_resolution_deg,
            "n_lat": self.n_lat,
            "n_lon": self.n_lon,
        }


@dataclass
class VariableSpec:
    """Describes one physical variable within a DataRecord."""

    name: str
    unit: str
    dtype: str
    valid_min: Optional[float] = None
    valid_max: Optional[float] = None
    fill_value: float = -9999.0
    description: str = ""


@dataclass
class QualityReport:
    """
    Produced by validation for every ingested batch. This is the thing M2
    (and later M4/M5) reads to decide whether to trust a given record.
    """

    source: SourceType
    generated_at: str
    timestamp_range: tuple  # (start_iso, end_iso)
    coverage_fraction: float          # fraction of expected timestamps present
    missing_fraction: float           # fraction of expected values that are missing/fill
    valid_fraction: float             # fraction of values within valid_min/valid_max
    schema_status: SchemaStatus
    quality_status: QualityStatus
    issues: list = field(default_factory=list)  # list[str] human-readable problems

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["source"] = self.source.value
        d["schema_status"] = self.schema_status.value
        d["quality_status"] = self.quality_status.value
        return d


@dataclass
class DataRecord:
    """
    The single unit of output M1 hands to M2. One DataRecord = one source,
    one contiguous batch of timestamps, one grid.

    `data` layout: for gridded sources (satellite, nwp, radar) this is a
    numpy array shaped [time, lat, lon, variables] (float32), with missing
    values represented as NaN (never a sentinel, once past raw ingestion —
    see docs/m1_m2_contract.md "missing value representation").

    For point sources (lightning) this is instead a structured record list
    exposed via `point_data`, since lightning strikes are not natively
    gridded; M1 does not grid/bin lightning data — that is an M2 feature-
    engineering step.
    """

    source: SourceType
    source_id: str                     # e.g. "insat3d", "gpm_imerg", "era5", "mock_demo"
    dataset_version: str                # adapter/dataset version string
    timestamps: list                    # list[str] ISO-8601 UTC, sorted, deduplicated
    grid: Optional[GridSpec]            # None for point data sources (e.g. lightning)
    variables: list                     # list[VariableSpec]
    data: Optional[np.ndarray]          # gridded array, or None for point sources
    point_data: Optional[list] = None   # list[dict] for point sources (lightning)
    quality: Optional[QualityReport] = None
    provenance: dict = field(default_factory=dict)

    def as_metadata_dict(self) -> dict:
        """Metadata-only view (no bulk array data) — what gets written as
        the .json sidecar next to every stored data file."""
        return {
            "source": self.source.value,
            "source_id": self.source_id,
            "dataset_version": self.dataset_version,
            "n_timestamps": len(self.timestamps),
            "timestamp_start": self.timestamps[0] if self.timestamps else None,
            "timestamp_end": self.timestamps[-1] if self.timestamps else None,
            "grid": self.grid.as_metadata_dict() if self.grid else None,
            "variables": [v.__dict__ for v in self.variables],
            "quality": self.quality.to_dict() if self.quality else None,
            "provenance": self.provenance,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
