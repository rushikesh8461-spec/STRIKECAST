"""
Phase 5 — Spatial alignment.

All four M1 gridded sources in this repository's demo config happen to
share one grid (config/ingestion_config.yaml `grid:`), but M2 must not
assume that in general (a real deployment could mix a native satellite
grid, an NWP model grid, and a radar composite grid). This module:

  1. Determines the target grid (config override, else whichever grid the
     gridded M1 sources already share).
  2. Regrids any gridded source onto the target grid — nearest-neighbor,
     the simplest reliable method for this repo's dependency footprint
     (no heavyweight geospatial libraries). A source already on the
     target grid takes a fast identity path (the common case here).
  3. Grids/bins the lightning point source onto the same target grid per
     common-grid timestamp (M1 explicitly does not do this — see
     docs/m1_m2_contract.md — it is an M2 feature-engineering step),
     producing per-cell strike_count and mean_abs_intensity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.ingestion.contract import GridSpec


@dataclass
class TargetGrid:
    lat_values: np.ndarray  # (n_lat,) ascending
    lon_values: np.ndarray  # (n_lon,) ascending
    lat_resolution_deg: float
    lon_resolution_deg: float

    @property
    def n_lat(self) -> int:
        return len(self.lat_values)

    @property
    def n_lon(self) -> int:
        return len(self.lon_values)


def determine_target_grid(
    gridded_records: dict, spatial_cfg: dict
) -> TargetGrid:
    override = spatial_cfg.get("target_grid")
    if override:
        lat_values = np.arange(
            override["lat_min"],
            override["lat_max"] + 1e-9,
            override["lat_resolution_deg"],
            dtype=np.float64,
        )
        lon_values = np.arange(
            override["lon_min"],
            override["lon_max"] + 1e-9,
            override["lon_resolution_deg"],
            dtype=np.float64,
        )
        return TargetGrid(
            lat_values=lat_values,
            lon_values=lon_values,
            lat_resolution_deg=override["lat_resolution_deg"],
            lon_resolution_deg=override["lon_resolution_deg"],
        )

    grids = [r.grid for r in gridded_records.values() if r.grid is not None]
    if not grids:
        raise ValueError(
            "No gridded M1 source available and no spatial_alignment.target_grid "
            "override configured — cannot determine a target grid."
        )
    reference: GridSpec = grids[0]
    for g in grids[1:]:
        if not (
            np.allclose(g.lat_values, reference.lat_values)
            and np.allclose(g.lon_values, reference.lon_values)
        ):
            # Sources disagree on grid: fall back to the reference grid and
            # let regrid_nearest() below handle the mismatch per-source,
            # rather than raising — heterogeneous native grids are the
            # normal case this function exists to handle.
            break
    return TargetGrid(
        lat_values=reference.lat_values,
        lon_values=reference.lon_values,
        lat_resolution_deg=reference.lat_resolution_deg,
        lon_resolution_deg=reference.lon_resolution_deg,
    )


def _grid_matches(src_lat, src_lon, target: TargetGrid) -> bool:
    return (
        len(src_lat) == target.n_lat
        and len(src_lon) == target.n_lon
        and np.allclose(src_lat, target.lat_values)
        and np.allclose(src_lon, target.lon_values)
    )


def regrid_nearest(
    data: np.ndarray,
    src_lat: np.ndarray,
    src_lon: np.ndarray,
    target: TargetGrid,
) -> np.ndarray:
    """Nearest-neighbor regrid `data` [time, lat, lon, var] from
    (src_lat, src_lon) onto `target`. Fast identity path when the grids
    already match exactly (the common case in this repo's demo data)."""
    if _grid_matches(src_lat, src_lon, target):
        return data

    lat_idx = np.searchsorted(src_lat, target.lat_values)
    lat_idx = np.clip(lat_idx, 1, len(src_lat) - 1)
    lat_left = lat_idx - 1
    lat_idx = np.where(
        np.abs(src_lat[lat_left] - target.lat_values)
        <= np.abs(src_lat[lat_idx] - target.lat_values),
        lat_left,
        lat_idx,
    )

    lon_idx = np.searchsorted(src_lon, target.lon_values)
    lon_idx = np.clip(lon_idx, 1, len(src_lon) - 1)
    lon_left = lon_idx - 1
    lon_idx = np.where(
        np.abs(src_lon[lon_left] - target.lon_values)
        <= np.abs(src_lon[lon_idx] - target.lon_values),
        lon_left,
        lon_idx,
    )

    return data[:, lat_idx, :, :][:, :, lon_idx, :]


def bin_lightning_to_grid(
    point_data: list[dict],
    common_grid: list[str],
    target: TargetGrid,
) -> tuple[np.ndarray, np.ndarray]:
    """Grid/bin lightning strikes onto (time, lat, lon) cells of the
    target grid. Returns (strike_count, mean_abs_intensity), each shaped
    [len(common_grid), n_lat, n_lon], float32. This is the M2-owned
    lightning-gridding step called out in docs/m1_m2_contract.md — M1
    deliberately leaves lightning as point data.

    Cell edges are placed halfway between grid-cell centers (standard
    nearest-cell binning); a strike exactly on a boundary falls into the
    lower-index cell (np.searchsorted default 'left' behavior via the
    edges array), which is an arbitrary-but-deterministic tie-break.
    """
    n_t = len(common_grid)
    n_lat, n_lon = target.n_lat, target.n_lon
    strike_count = np.zeros((n_t, n_lat, n_lon), dtype=np.float32)
    intensity_sum = np.zeros((n_t, n_lat, n_lon), dtype=np.float64)

    if not point_data:
        return strike_count, np.zeros_like(strike_count)

    time_index = {ts: i for i, ts in enumerate(common_grid)}

    lat_edges = np.concatenate(
        [[-90.0], (target.lat_values[:-1] + target.lat_values[1:]) / 2.0, [90.0]]
    )
    lon_edges = np.concatenate(
        [[-180.0], (target.lon_values[:-1] + target.lon_values[1:]) / 2.0, [180.0]]
    )

    for p in point_data:
        t_idx = time_index.get(p["timestamp"])
        if t_idx is None:
            continue  # already dropped/unmatched by temporal alignment
        lat_idx = int(np.clip(np.searchsorted(lat_edges, p["latitude"]) - 1, 0, n_lat - 1))
        lon_idx = int(np.clip(np.searchsorted(lon_edges, p["longitude"]) - 1, 0, n_lon - 1))
        strike_count[t_idx, lat_idx, lon_idx] += 1.0
        intensity = p.get("intensity")
        if intensity is not None and np.isfinite(intensity):
            intensity_sum[t_idx, lat_idx, lon_idx] += abs(float(intensity))

    with np.errstate(invalid="ignore", divide="ignore"):
        mean_abs_intensity = np.where(
            strike_count > 0, intensity_sum / np.maximum(strike_count, 1), 0.0
        ).astype(np.float32)

    return strike_count, mean_abs_intensity
