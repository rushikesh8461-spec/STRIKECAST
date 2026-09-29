"""
LightningDataSource

MVP STATUS: demo/synthetic only (MISSING — no real lightning network feed,
e.g. ISRO/IMD LLDN or WWLLN, integrated in this repository).

Unlike the gridded sources, lightning strikes are inherently point data
(irregular lat/lon/time), so this adapter does NOT populate DataRecord.grid
or DataRecord.data — it populates DataRecord.point_data. Gridding/binning
lightning strikes onto the model grid is explicitly an M2 feature-engineering
step (see docs/m1_m2_contract.md), not an M1 responsibility.
"""

from __future__ import annotations

import numpy as np

from ..base import BaseDataSource
from ..contract import DataRecord, SourceType, VariableSpec
from ..metadata import build_provenance
from ..validation.temporal import validate_temporal
from ..validation.spatial import validate_point_coordinates
from ..validation.quality import compute_quality_report
from ._grid_utils import build_timestamps


class LightningDataSource(BaseDataSource):
    source_type = SourceType.LIGHTNING
    SOURCE_ID = "mock_lightning_network_v1"
    DATASET_VERSION = "0.1.0-demo"

    def get_schema(self) -> list[VariableSpec]:
        return [
            VariableSpec(
                name="intensity",
                unit="kA",
                dtype="float32",
                valid_min=-500.0,
                valid_max=500.0,
                description="Peak current estimate (signed; sign encodes polarity where available).",
            ),
        ]

    def normalize_metadata(self) -> dict:
        return build_provenance(
            source_id=self.SOURCE_ID,
            dataset_version=self.DATASET_VERSION,
            acquisition_method="synthetic_generator" if self.demo else "NOT_IMPLEMENTED",
            is_synthetic=self.demo,
            notes=(
                "Deterministic synthetic point-process strike data for SIH demo."
                if self.demo
                else "No real lightning network feed implemented in this repository."
            ),
        )

    def load(self) -> dict:
        if not self.demo:
            raise NotImplementedError(
                "Real lightning ingestion is not implemented in this repository "
                "(MISSING — see Phase 1 audit). Instantiate with demo=True."
            )
        grid_cfg = self.config.grid_spec_dict()
        demo_cfg = self.config.demo_dataset_params()
        timestamps = build_timestamps(demo_cfg)
        rng = np.random.default_rng(demo_cfg["random_seed"] + 2)

        mean_strikes = demo_cfg["lightning_strikes_per_timestep_mean"]
        points = []
        for ts in timestamps:
            n_strikes = int(rng.poisson(mean_strikes))
            # Cluster strikes loosely around the same drifting "storm cell"
            # used by the satellite adapter, so the two sources are at least
            # spatially plausible together in the demo (not physically coupled,
            # this is a demo-data convenience only).
            center_lat = rng.uniform(grid_cfg["lat_min"] + 0.5, grid_cfg["lat_max"] - 0.5)
            center_lon = rng.uniform(grid_cfg["lon_min"] + 0.5, grid_cfg["lon_max"] - 0.5)
            lats = np.clip(rng.normal(center_lat, 0.4, n_strikes), grid_cfg["lat_min"], grid_cfg["lat_max"])
            lons = np.clip(rng.normal(center_lon, 0.4, n_strikes), grid_cfg["lon_min"], grid_cfg["lon_max"])
            intensities = rng.normal(0, 25, n_strikes)  # signed kA, sign ~ polarity
            for lat, lon, inten in zip(lats, lons, intensities):
                points.append(
                    {
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "timestamp": ts,
                        "intensity": float(inten),
                        "polarity": "negative" if inten < 0 else "positive",
                    }
                )
        return {"timestamps": timestamps, "points": points}

    def validate(self, raw: dict):
        temporal_cfg = self.config.demo_dataset_params()
        temporal_result = validate_temporal(
            raw["timestamps"], expected_timestep_minutes=temporal_cfg["timestep_minutes"]
        )
        if raw["points"]:
            lats = np.array([p["latitude"] for p in raw["points"]])
            lons = np.array([p["longitude"] for p in raw["points"]])
            spatial_result = validate_point_coordinates(lats, lons)
            intensities = np.array([p["intensity"] for p in raw["points"]])
            missing_fraction = float(np.mean(~np.isfinite(intensities)))
        else:
            spatial_result = {"valid": True, "issues": ["No strikes recorded in this window."], "n_points": 0}
            missing_fraction = 0.0

        thresholds = self.config.quality_thresholds()
        return compute_quality_report(
            source=self.source_type,
            temporal_result=temporal_result,
            spatial_result=spatial_result,
            schema_result=None,  # point data: no fixed array schema to check
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
            grid=None,
            variables=self.get_schema(),
            data=None,
            point_data=raw["points"],
            quality=quality,
            provenance=provenance,
        )
