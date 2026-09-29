import numpy as np

from src.ingestion.validation.spatial import validate_spatial, validate_point_coordinates


def test_valid_grid():
    lat = np.arange(18.0, 22.01, 0.25)
    lon = np.arange(77.0, 81.01, 0.25)
    result = validate_spatial(lat, lon, expected_lat_resolution_deg=0.25, expected_lon_resolution_deg=0.25)
    assert result["valid"] is True
    assert result["n_lat"] == len(lat)
    assert result["n_lon"] == len(lon)


def test_out_of_range_latitude_flagged():
    lat = np.array([18.0, 95.0, 20.0])  # 95 is invalid
    lon = np.array([77.0, 78.0, 79.0])
    result = validate_spatial(lat, lon)
    assert result["valid"] is False
    assert any("latitude" in i.lower() for i in result["issues"])


def test_non_monotonic_lon_flagged():
    lat = np.array([18.0, 18.5, 19.0])
    lon = np.array([77.0, 79.0, 78.0])  # not monotonic
    result = validate_spatial(lat, lon)
    assert result["lon_monotonic"] is False
    assert result["valid"] is False


def test_resolution_mismatch_flagged():
    lat = np.array([18.0, 18.5, 19.0])
    lon = np.array([77.0, 77.5, 78.0])
    result = validate_spatial(lat, lon, expected_lat_resolution_deg=0.1)
    assert result["valid"] is False


def test_point_coordinates_valid():
    lats = np.array([18.5, 19.0, 20.1])
    lons = np.array([77.5, 78.0, 79.9])
    result = validate_point_coordinates(lats, lons)
    assert result["valid"] is True
    assert result["n_points"] == 3


def test_point_coordinates_invalid():
    lats = np.array([18.5, 999.0])
    lons = np.array([77.5, 78.0])
    result = validate_point_coordinates(lats, lons)
    assert result["valid"] is False
