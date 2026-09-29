"""
NWPDataSource

MVP STATUS: demo/synthetic only (MISSING — no real NWP feed, e.g. NCMRWF/
IMD GFS/ERA5 GRIB or NetCDF ingestion, implemented in this repository).

Produces a gridded synthetic field for temperature, humidity, pressure,
wind (u/v), CAPE, and CIN — the variables listed as "potential" in the
spec's Phase 2 conceptual-sources section. Precipitation-related NWP
variables are marked as a Future/advanced item (see Phase 13 report):
including them redundantly with radar in the MVP was judged unnecessary
scope for the demo.
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


class NWPDataSource(BaseDataSource):
    source_type = SourceType.NWP
    SOURCE_ID = "mock_nwp_reanalysis_v1"
    DATASET_VERSION = "0.1.0-demo"

    def get_schema(self) -> list[VariableSpec]:
        return [
            VariableSpec("temperature_2m", "K", "float32", 200.0, 330.0,
                         description="2m air temperature."),
            VariableSpec("relative_humidity", "%", "float32", 0.0, 100.0,
                         description="Relative humidity."),
            VariableSpec("surface_pressure", "hPa", "float32", 850.0, 1050.0,
                         description="Surface-level pressure."),
            VariableSpec("wind_u", "m/s", "float32", -60.0, 60.0,
                         description="Eastward wind component (10m)."),
            VariableSpec("wind_v", "m/s", "float32", -60.0, 60.0,
                         description="Northward wind component (10m)."),
            VariableSpec("cape", "J/kg", "float32", 0.0, 8000.0,
                         description="Convective Available Potential Energy."),
            VariableSpec("cin", "J/kg", "float32", -1000.0, 0.0,
                         description="Convective Inhibition."),
        ]

    def normalize_metadata(self) -> dict:
        return build_provenance(
            source_id=self.SOURCE_ID,
            dataset_version=self.DATASET_VERSION,
            acquisition_method="synthetic_generator" if self.demo else "NOT_IMPLEMENTED",
            is_synthetic=self.demo,
            notes=(
                "Deterministic synthetic NWP-like field for SIH demo."
                if self.demo
                else "No real NWP feed implemented in this repository."
            ),
        )

    def load(self) -> dict:
        if not self.demo:
            raise NotImplementedError(
                "Real NWP ingestion is not implemented in this repository "
                "(MISSING — see Phase 1 audit). Instantiate with demo=True."
            )
        grid_cfg = self.config.grid_spec_dict()
        demo_cfg = self.config.demo_dataset_params()
        grid = build_grid(grid_cfg)
        timestamps = build_timestamps(demo_cfg)
        rng = np.random.default_rng(demo_cfg["random_seed"] + 3)

        n_t, n_lat, n_lon = len(timestamps), grid.n_lat, grid.n_lon
        variables = self.get_schema()
        data = np.empty((n_t, n_lat, n_lon, len(variables)), dtype=np.float32)

        lat_grid, lon_grid = np.meshgrid(grid.lat_values, grid.lon_values, indexing="ij")
        for t in range(n_t):
            # Rising CAPE / falling CIN over the window -> a plausible
            # "building instability ahead of a storm" synthetic signal.
            frac = t / max(n_t - 1, 1)
            data[t, :, :, 0] = 301.0 - 0.3 * (lat_grid - grid.lat_min) + rng.normal(0, 1.0, (n_lat, n_lon))
            data[t, :, :, 1] = np.clip(55 + 25 * frac + rng.normal(0, 5, (n_lat, n_lon)), 0, 100)
            data[t, :, :, 2] = 1008.0 - 4.0 * frac + rng.normal(0, 1.5, (n_lat, n_lon))
            data[t, :, :, 3] = 3.0 + 4.0 * frac + rng.normal(0, 1.0, (n_lat, n_lon))
            data[t, :, :, 4] = -2.0 + 3.0 * frac + rng.normal(0, 1.0, (n_lat, n_lon))
            data[t, :, :, 5] = np.clip(400 + 2500 * frac + rng.normal(0, 200, (n_lat, n_lon)), 0, None)
            data[t, :, :, 6] = -np.clip(150 - 100 * frac + rng.normal(0, 20, (n_lat, n_lon)), 0, None)

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
