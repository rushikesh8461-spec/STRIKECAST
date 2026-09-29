from __future__ import annotations

import shutil

import pytest

netcdf4 = pytest.importorskip("netCDF4")

from scripts.data.inventory_uploaded_data import build_inventory, sha256  # noqa: E402


def _write_minimal_lis_file(path):
    with netcdf4.Dataset(path, "w") as ds:
        ds.createDimension("viewtime_dim", 1)
        ds.createDimension("flash_dim", 0)
        ds.createDimension("event_dim", 0)
        for name, dtype, value in (
            ("orbit_summary_id_number", "i4", 10),
            ("orbit_summary_TAI93_start", "f8", 10.0),
            ("orbit_summary_TAI93_end", "f8", 20.0),
            ("orbit_summary_start_longitude", "f4", 1.0),
            ("orbit_summary_end_longitude", "f4", 2.0),
            ("point_summary_flash_count", "i4", 0),
            ("point_summary_group_count", "i4", 0),
            ("point_summary_event_count", "i4", 0),
            ("point_summary_vt_count", "i4", 1),
        ):
            ds.createVariable(name, dtype)[...] = value
        ds.createVariable("orbit_summary_UTC_start", str)[...] = "2023-11-16T00:00:00Z"
        for name, dtype, values in (
            ("viewtime_lat", "f4", [10.0]), ("viewtime_lon", "f4", [20.0]),
            ("viewtime_TAI93_start", "f8", [10.0]), ("viewtime_TAI93_end", "f8", [20.0]),
            ("viewtime_effective_obs", "f4", [10.0]), ("viewtime_alert_flag", "u1", [2]),
            ("lightning_flash_lat", "f4", []), ("lightning_flash_lon", "f4", []),
            ("lightning_flash_alert_flag", "u1", []), ("lightning_event_alert_flag", "u1", []),
        ):
            dim = "viewtime_dim" if name.startswith("viewtime_") else ("flash_dim" if "flash" in name else "event_dim")
            ds.createVariable(name, dtype, (dim,))[:] = values


def test_inventory_hashes_netcdf_and_marks_duplicate_source_content(tmp_path):
    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    lightning = raw / "lightning"
    lightning.mkdir(parents=True)
    interim.mkdir()
    first = lightning / "orbit.nc"
    _write_minimal_lis_file(first)
    duplicate = lightning / "orbit-copy.nc"
    shutil.copyfile(first, duplicate)

    result = build_inventory(raw, interim)

    assert len(result["files"]) == 2
    assert result["files"][0]["netcdf"]["orbit_id"] == 10
    assert result["files"][0]["netcdf"]["viewtime_count"] == 1
    assert result["files"][0]["sha256"] == sha256(first)
    assert result["files"][1]["duplicate_content"] is True
