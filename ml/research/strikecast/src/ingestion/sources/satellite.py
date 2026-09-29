"""
SatelliteDataSource

MVP STATUS: demo/synthetic only. No real satellite API/file-format
integration exists in this repository (see repository audit, Phase 1 —
MISSING — NOT PRESENT IN REPOSITORY). This adapter generates a
deterministic, seeded synthetic IR/brightness-temperature field so the
full pipeline (M1 -> M2 -> ... -> M6) is runnable end-to-end offline.

Real satellite ingestion (e.g. INSAT-3D/3DR IR channels via ISRO/MOSDAC, or
GOES/Himawari) is a documented Future/advanced item — see docs and the
Phase-13 report's "Known limitations" section. Swapping in a real adapter
only requires implementing `load()` differently; `validate()`,
`normalize_metadata()`, `get_schema()`, and `get_record()` are written
against the contract, not against the synthetic generator.
"""

from __future__ import annotations

import numpy as np

from ..base import BaseDataSource
from ..contract import DataRecord, SourceType, VariableSpec
from ..metadata import build_provenance
from ..validation.temporal import validate_temporal
from ..validation.spatial import validate_spatial
from ..validation.schema import validate_schema
from ..validation.quality import compute_missing_fraction, compute_quality_report
from ._grid_utils import build_grid, build_timestamps


class SatelliteDataSource(BaseDataSource):
    source_type = SourceType.SATELLITE
    SOURCE_ID = "mock_geostationary_ir_v1"
    DATASET_VERSION = "0.1.0-demo"

    def get_schema(self) -> list[VariableSpec]:
        return [
            VariableSpec(
                name="brightness_temperature",
                unit="K",
                dtype="float32",
                valid_min=170.0,
                valid_max=330.0,
                fill_value=-9999.0,
                description="IR channel brightness temperature (cloud-top proxy).",
            ),
            VariableSpec(
                name="cloud_top_height_estimate",
                unit="km",
                dtype="float32",
                valid_min=0.0,
                valid_max=20.0,
                fill_value=-9999.0,
                description="Derived cloud-top height estimate from brightness temperature.",
            ),
        ]

    def normalize_metadata(self) -> dict:
        return build_provenance(
            source_id=self.SOURCE_ID,
            dataset_version=self.DATASET_VERSION,
            acquisition_method="synthetic_generator" if self.demo else "NOT_IMPLEMENTED",
            is_synthetic=self.demo,
            notes=(
                "Deterministic synthetic IR field for SIH demo/offline pipeline testing."
                if self.demo
                else "No real acquisition path implemented in this repository."
            ),
        )

    def load(self) -> dict:
        if not self.demo:
            raise NotImplementedError(
                "Real satellite ingestion is not implemented in this repository "
                "(MISSING — see Phase 1 audit). Instantiate with demo=True."
            )
        grid_cfg = self.config.grid_spec_dict()
        demo_cfg = self.config.demo_dataset_params()
        grid = build_grid(grid_cfg)
        timestamps = build_timestamps(demo_cfg)

        rng = np.random.default_rng(demo_cfg["random_seed"] + 1)  # +1: distinct stream per source
        n_t, n_lat, n_lon = len(timestamps), grid.n_lat, grid.n_lon

        # Simple synthetic convective-cell pattern: a cold (storm-like) blob
        # that drifts across the grid over time, plus background warm field.
        lat_grid, lon_grid = np.meshgrid(grid.lat_values, grid.lon_values, indexing="ij")
        bt = np.empty((n_t, n_lat, n_lon), dtype=np.float32)
        cth = np.empty((n_t, n_lat, n_lon), dtype=np.float32)
        for t in range(n_t):
            center_lat = grid.lat_min + (grid.lat_max - grid.lat_min) * (0.3 + 0.4 * t / max(n_t - 1, 1))
            center_lon = grid.lon_min + (grid.lon_max - grid.lon_min) * (0.2 + 0.6 * t / max(n_t - 1, 1))
            dist2 = (lat_grid - center_lat) ** 2 + (lon_grid - center_lon) ** 2
            cold_blob = 60.0 * np.exp(-dist2 / (2 * 0.6 ** 2))
            noise = rng.normal(0, 2.0, size=(n_lat, n_lon))
            bt[t] = 290.0 - cold_blob + noise
            cth[t] = np.clip(cold_blob / 5.0 + rng.normal(0, 0.3, size=(n_lat, n_lon)), 0, None)

        data = np.stack([bt, cth], axis=-1)  # [time, lat, lon, variables]

        # Inject a small, deterministic fraction of missing values to make
        # validation/quality-check behavior demonstrable.
        missing_mask = rng.random(data.shape[:-1]) < 0.01
        data[missing_mask, :] = np.nan

        return {"grid": grid, "timestamps": timestamps, "data": data}

    def validate(self, raw: dict):
        temporal_cfg = self.config.demo_dataset_params()
        temporal_result = validate_temporal(
            raw["timestamps"], expected_timestep_minutes=temporal_cfg["timestep_minutes"]
        )
        spatial_result = validate_spatial(
            raw["grid"].lat_values,
            raw["grid"].lon_values,
            expected_lat_resolution_deg=raw["grid"].lat_resolution_deg,
            expected_lon_resolution_deg=raw["grid"].lon_resolution_deg,
        )
        schema_result = validate_schema(
            raw["data"],
            self.get_schema(),
            expected_shape_prefix=(len(raw["timestamps"]), raw["grid"].n_lat, raw["grid"].n_lon),
        )
        missing_fraction = compute_missing_fraction(raw["data"])
        thresholds = self.config.quality_thresholds()
        return compute_quality_report(
            source=self.source_type,
            temporal_result=temporal_result,
            spatial_result=spatial_result,
            schema_result=schema_result,
            missing_fraction=missing_fraction,
            degraded_missing_fraction=thresholds["degraded_missing_fraction"],
            failed_missing_fraction=thresholds["failed_missing_fraction"],
            min_coverage_fraction=thresholds["min_coverage_fraction"],
        )

    def get_record(self) -> DataRecord:
        raw = self.load()
        quality = self.validate(raw)
        provenance = self.normalize_metadata()
        return DataRecord(
            source=self.source_type,
            source_id=self.SOURCE_ID,
            dataset_version=self.DATASET_VERSION,
            timestamps=raw["timestamps"],
            grid=raw["grid"],
            variables=self.get_schema(),
            data=raw["data"],
            quality=quality,
            provenance=provenance,
        )
