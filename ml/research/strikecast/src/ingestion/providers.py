"""Typed provider boundary and provenance validator for observational inputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .contract import DataRecord


@dataclass(frozen=True)
class ProviderMetadata:
    source: str
    provider: str
    license: str
    coverage: dict
    cadence_minutes: float
    spatial_resolution_deg: float
    variables: tuple[str, ...]
    units: dict[str, str]
    time_range: tuple[str, str]
    geographic_range: dict[str, tuple[float, float]]
    checksum: str
    dataset_version: str

    def validate(self) -> None:
        required = (self.source, self.provider, self.license, self.dataset_version, self.checksum)
        if any(not value.strip() for value in required):
            raise ValueError("Provider provenance source/provider/license/version/checksum are required")
        if self.cadence_minutes <= 0 or self.spatial_resolution_deg <= 0:
            raise ValueError("Provider cadence and spatial resolution must be positive")
        if not self.variables or set(self.variables) != set(self.units) or any(not self.units[v] for v in self.variables):
            raise ValueError("Provider variables and units must be non-empty and correspond exactly")
        if len(self.time_range) != 2 or not all(self.time_range):
            raise ValueError("Provider time range must include start and end")
        if not {"lat", "lon"}.issubset(self.geographic_range):
            raise ValueError("Provider geographic range must include latitude and longitude bounds")
        if not self.coverage:
            raise ValueError("Provider coverage metadata is required")


@runtime_checkable
class AtmosphericProvider(Protocol):
    metadata: ProviderMetadata

    def fetch(self, start_time: str, end_time: str, geographic_range: dict) -> DataRecord: ...


@runtime_checkable
class LightningProvider(Protocol):
    metadata: ProviderMetadata

    def fetch(self, start_time: str, end_time: str, geographic_range: dict) -> DataRecord: ...


@runtime_checkable
class DatasetProvider(Protocol):
    """Canonical read-only boundary for source-specific dataset adapters."""

    def inventory(self) -> list[dict[str, Any]]: ...
    def validate(self) -> list[dict[str, Any]]: ...
    def manifest(self) -> dict[str, Any]: ...
    def coverage(self) -> dict[str, Any]: ...
    def schema(self) -> dict[str, Any]: ...
    def checksum(self, source: str) -> str: ...
    def load(self, source: str) -> Any: ...
    def provenance(self, source: str) -> dict[str, Any]: ...
