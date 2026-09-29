"""
BaseDataSource — the common interface every M1 source adapter implements.

Design intent (Phase 5): keep this minimal and SIH-demo friendly. Each
concrete adapter (SatelliteDataSource, LightningDataSource, NWPDataSource,
RadarDataSource) implements:

    load()               -> raw, adapter-native data (may be mocked/synthetic)
    validate(raw)         -> QualityReport
    normalize_metadata()  -> dict of standardized metadata fields
    get_schema()          -> list[VariableSpec] this adapter promises to produce

and a single public entry point `get_record()` that ties these together and
returns a DataRecord conforming to the M1 -> M2 contract (contract.py).

No source-specific logic (real API calls, file-format parsing, etc.) lives
here — this class only defines and enforces the shape of the contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .contract import DataRecord, QualityReport, SourceType, VariableSpec


class BaseDataSource(ABC):
    """Abstract base for all M1 data source adapters."""

    #: Subclasses must set this to one of SourceType.
    source_type: SourceType

    def __init__(self, config: Any, demo: bool = False):
        """
        Parameters
        ----------
        config : IngestionConfig
            Loaded configuration (see config.py). Never hard-code paths.
        demo : bool
            If True, adapter reads/generates from the sample_demo directory
            instead of the raw/ directory. MVP adapters in this repository
            are demo-only (see PROBLEMS/MISSING notes in the audit); real
            external-source implementations are a documented future step.
        """
        self.config = config
        self.demo = demo

    @abstractmethod
    def load(self) -> Any:
        """Acquire raw, adapter-native data. Must not raise on missing
        optional data — return an empty-but-well-formed structure and let
        validate() flag it via QualityReport instead, so one bad source
        never crashes the whole ingestion run."""
        raise NotImplementedError

    @abstractmethod
    def validate(self, raw: Any) -> QualityReport:
        """Run temporal/spatial/schema/missing-data validation over `raw`
        and return a QualityReport. Must not mutate `raw`."""
        raise NotImplementedError

    @abstractmethod
    def normalize_metadata(self) -> dict:
        """Return the standardized metadata fields (source_id, dataset
        version, provenance dict) for this adapter — independent of any
        single load() call's data."""
        raise NotImplementedError

    @abstractmethod
    def get_schema(self) -> list[VariableSpec]:
        """Return the list of VariableSpec this adapter's DataRecord.data
        (or point_data) will contain."""
        raise NotImplementedError

    @abstractmethod
    def get_record(self) -> DataRecord:
        """Public entry point. Ties load() + validate() + normalize_metadata()
        + get_schema() together into one DataRecord conforming to the M1 ->
        M2 contract. This is the ONLY method M2-facing code (and the CLI /
        tests) should call directly."""
        raise NotImplementedError
