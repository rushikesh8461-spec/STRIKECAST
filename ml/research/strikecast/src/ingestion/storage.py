"""
Raw-data caching / storage strategy (Phase 8 of the spec / M1 responsibility
#12-13: "Raw-data caching/storage strategy" and "Reproducible data loading").

Storage convention (documented fully in docs/m1_m2_contract.md):

    <data_root>/<raw|sample_demo>/<source>/<source_id>_<start>_<end>.npz
    <data_root>/<raw|sample_demo>/<source>/<source_id>_<start>_<end>.json   (metadata sidecar)

- .npz holds the gridded array (or point arrays for lightning), plus lat/lon
  coordinate arrays, using numpy's compressed format — simple, dependency-free,
  and sufficient for MVP/demo data volumes.
- .json holds DataRecord.as_metadata_dict() — human-readable, git-diffable,
  and readable without loading the (potentially large) array.

This is intentionally simple (Phase 5 note: "do not create unnecessary
abstraction"). A production system would likely move to Zarr/NetCDF for the
gridded sources; that is called out as a Future/advanced item, not blocking
the MVP.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .contract import DataRecord, GridSpec, QualityReport, QualityStatus, SchemaStatus, SourceType, VariableSpec


def _filename_stub(record: DataRecord) -> str:
    start = record.timestamps[0].replace(":", "").replace("-", "") if record.timestamps else "na"
    end = record.timestamps[-1].replace(":", "").replace("-", "") if record.timestamps else "na"
    return f"{record.source_id}_{start}_{end}"


def save_record(record: DataRecord, directory: Path) -> tuple[Path, Path]:
    """Save a DataRecord's array + metadata sidecar under `directory`.
    Returns (npz_path, json_path)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stub = _filename_stub(record)
    npz_path = directory / f"{stub}.npz"
    json_path = directory / f"{stub}.json"

    save_kwargs = {"timestamps": np.array(record.timestamps)}
    if record.grid is not None:
        save_kwargs["lat_values"] = record.grid.lat_values
        save_kwargs["lon_values"] = record.grid.lon_values
    if record.data is not None:
        save_kwargs["data"] = record.data
    if record.point_data is not None:
        # Structured point data (lightning): store as separate arrays.
        save_kwargs["point_lat"] = np.array([p["latitude"] for p in record.point_data])
        save_kwargs["point_lon"] = np.array([p["longitude"] for p in record.point_data])
        save_kwargs["point_time"] = np.array([p["timestamp"] for p in record.point_data])
        save_kwargs["point_intensity"] = np.array(
            [p.get("intensity", np.nan) for p in record.point_data]
        )
        save_kwargs["point_polarity"] = np.array(
            [p.get("polarity", "") for p in record.point_data]
        )

    np.savez_compressed(npz_path, **save_kwargs)
    with open(json_path, "w") as f:
        json.dump(record.as_metadata_dict(), f, indent=2, default=str)

    return npz_path, json_path


def load_record(npz_path: Path, json_path: Path | None = None) -> DataRecord:
    """Reload a DataRecord previously written by save_record(). This is the
    'reproducible data loading' entry point referenced throughout the spec."""
    npz_path = Path(npz_path)
    json_path = Path(json_path) if json_path else npz_path.with_suffix(".json")

    with open(json_path, "r") as f:
        meta = json.load(f)

    npz = np.load(npz_path, allow_pickle=False)
    timestamps = [str(t) for t in npz["timestamps"]]

    grid = None
    if meta.get("grid") is not None:
        g = meta["grid"]
        grid = GridSpec(
            lat_min=g["lat_min"],
            lat_max=g["lat_max"],
            lon_min=g["lon_min"],
            lon_max=g["lon_max"],
            lat_resolution_deg=g["lat_resolution_deg"],
            lon_resolution_deg=g["lon_resolution_deg"],
            n_lat=g["n_lat"],
            n_lon=g["n_lon"],
            lat_values=npz["lat_values"],
            lon_values=npz["lon_values"],
        )

    variables = [
        VariableSpec(
            name=v["name"],
            unit=v["unit"],
            dtype=v["dtype"],
            valid_min=v.get("valid_min"),
            valid_max=v.get("valid_max"),
            fill_value=v.get("fill_value", -9999.0),
            description=v.get("description", ""),
        )
        for v in meta["variables"]
    ]

    data = npz["data"] if "data" in npz.files else None

    point_data = None
    if "point_lat" in npz.files:
        point_data = [
            {
                "latitude": float(lat),
                "longitude": float(lon),
                "timestamp": str(t),
                "intensity": float(i) if not np.isnan(i) else None,
                "polarity": str(p) if p else None,
            }
            for lat, lon, t, i, p in zip(
                npz["point_lat"],
                npz["point_lon"],
                npz["point_time"],
                npz["point_intensity"],
                npz["point_polarity"],
            )
        ]

    quality = None
    if meta.get("quality") is not None:
        q = meta["quality"]
        quality = QualityReport(
            source=SourceType(q["source"]),
            generated_at=q["generated_at"],
            timestamp_range=tuple(q["timestamp_range"]),
            coverage_fraction=q["coverage_fraction"],
            missing_fraction=q["missing_fraction"],
            valid_fraction=q["valid_fraction"],
            schema_status=SchemaStatus(q["schema_status"]),
            quality_status=QualityStatus(q["quality_status"]),
            issues=q.get("issues", []),
        )

    return DataRecord(
        source=SourceType(meta["source"]),
        source_id=meta["source_id"],
        dataset_version=meta["dataset_version"],
        timestamps=timestamps,
        grid=grid,
        variables=variables,
        data=data,
        point_data=point_data,
        quality=quality,
        provenance=meta.get("provenance", {}),
    )
