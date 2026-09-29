"""Spatial validation (Phase 6): lat/lon range, grid dims, resolution."""

from __future__ import annotations

import numpy as np


def validate_spatial(
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    expected_lat_resolution_deg: float | None = None,
    expected_lon_resolution_deg: float | None = None,
) -> dict:
    """
    Returns a dict:
        valid: bool
        issues: list[str]
        lat_range: (min, max)
        lon_range: (min, max)
        n_lat: int
        n_lon: int
        lat_monotonic: bool
        lon_monotonic: bool
    """
    issues: list[str] = []

    lat_ok = np.all((lat_values >= -90.0) & (lat_values <= 90.0))
    if not lat_ok:
        issues.append("One or more latitude values outside valid range [-90, 90].")

    lon_ok = np.all((lon_values >= -180.0) & (lon_values <= 180.0))
    if not lon_ok:
        issues.append("One or more longitude values outside valid range [-180, 180].")

    lat_monotonic = bool(np.all(np.diff(lat_values) > 0) or np.all(np.diff(lat_values) < 0))
    lon_monotonic = bool(np.all(np.diff(lon_values) > 0) or np.all(np.diff(lon_values) < 0))
    if not lat_monotonic:
        issues.append("Latitude values are not monotonic.")
    if not lon_monotonic:
        issues.append("Longitude values are not monotonic.")

    if expected_lat_resolution_deg is not None and len(lat_values) > 1:
        actual_res = float(abs(np.mean(np.diff(lat_values))))
        if abs(actual_res - expected_lat_resolution_deg) > 1e-6:
            issues.append(
                f"Latitude resolution {actual_res:.4f} deg does not match "
                f"expected {expected_lat_resolution_deg:.4f} deg."
            )

    if expected_lon_resolution_deg is not None and len(lon_values) > 1:
        actual_res = float(abs(np.mean(np.diff(lon_values))))
        if abs(actual_res - expected_lon_resolution_deg) > 1e-6:
            issues.append(
                f"Longitude resolution {actual_res:.4f} deg does not match "
                f"expected {expected_lon_resolution_deg:.4f} deg."
            )

    valid = lat_ok and lon_ok and lat_monotonic and lon_monotonic and not issues

    return {
        "valid": bool(valid),
        "issues": issues,
        "lat_range": (float(np.min(lat_values)), float(np.max(lat_values))),
        "lon_range": (float(np.min(lon_values)), float(np.max(lon_values))),
        "n_lat": int(len(lat_values)),
        "n_lon": int(len(lon_values)),
        "lat_monotonic": lat_monotonic,
        "lon_monotonic": lon_monotonic,
    }


def validate_point_coordinates(lats: np.ndarray, lons: np.ndarray) -> dict:
    """Spatial validation for point data (e.g. lightning strikes) that are
    not on a grid — just range-checks each point."""
    issues: list[str] = []
    lat_ok = np.all((lats >= -90.0) & (lats <= 90.0))
    lon_ok = np.all((lons >= -180.0) & (lons <= 180.0))
    if not lat_ok:
        issues.append("One or more strike latitudes outside valid range [-90, 90].")
    if not lon_ok:
        issues.append("One or more strike longitudes outside valid range [-180, 180].")
    return {
        "valid": bool(lat_ok and lon_ok),
        "issues": issues,
        "n_points": int(len(lats)),
    }
