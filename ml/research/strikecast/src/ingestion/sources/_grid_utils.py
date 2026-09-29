"""Internal helpers shared by gridded source adapters (satellite/nwp/radar).
Not part of the public M1 -> M2 contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from ..contract import GridSpec


def build_grid(grid_cfg: dict) -> GridSpec:
    lat_values = np.arange(
        grid_cfg["lat_min"],
        grid_cfg["lat_max"] + 1e-9,
        grid_cfg["lat_resolution_deg"],
        dtype=np.float64,
    )
    lon_values = np.arange(
        grid_cfg["lon_min"],
        grid_cfg["lon_max"] + 1e-9,
        grid_cfg["lon_resolution_deg"],
        dtype=np.float64,
    )
    return GridSpec(
        lat_min=grid_cfg["lat_min"],
        lat_max=grid_cfg["lat_max"],
        lon_min=grid_cfg["lon_min"],
        lon_max=grid_cfg["lon_max"],
        lat_resolution_deg=grid_cfg["lat_resolution_deg"],
        lon_resolution_deg=grid_cfg["lon_resolution_deg"],
        n_lat=len(lat_values),
        n_lon=len(lon_values),
        lat_values=lat_values,
        lon_values=lon_values,
    )


def build_timestamps(demo_cfg: dict) -> list[str]:
    start = datetime.fromisoformat(demo_cfg["start_time_utc"].replace("Z", "+00:00"))
    step = timedelta(minutes=demo_cfg["timestep_minutes"])
    n = demo_cfg["n_timestamps"]
    return [
        (start + i * step).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(n)
    ]
