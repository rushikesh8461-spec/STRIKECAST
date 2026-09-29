"""Small TEST-only fixtures for raw source decoder mechanics; not science data."""
from pathlib import Path
import numpy as np
import pytest

netCDF4 = pytest.importorskip("netCDF4")
from ml.research.strikecast.src.ingestion.provider_adapters import LISProvider


def _fixture(path: Path, *, omit=None):
    with netCDF4.Dataset(path, "w", format="NETCDF4") as ds:
        ds.createDimension("view", 2)
        ds.createDimension("event", 1)
        for name, dim, vals, dtype in [
            ("viewtime_lat","view",[8.25,8.25],"f4"),("viewtime_lon","view",[72.25,72.25],"f4"),
            ("viewtime_TAI93_start","view",[1.,60.],"f8"),("viewtime_TAI93_end","view",[59.,119.],"f8"),
            ("viewtime_effective_obs","view",[58.,59.],"f4"),("viewtime_alert_flag","view",[0,2],"u1"),
            ("lightning_event_lat","event",[8.25],"f4"),("lightning_event_lon","event",[72.25],"f4"),
            ("lightning_event_TAI93_time","event",[42.],"f8"),("lightning_event_alert_flag","event",[0],"u1")]:
            if name == omit: continue
            v=ds.createVariable(name,dtype,(dim,)); v[:]=vals
            if "alert_flag" in name: v.comment="fixture quality flag metadata"
        ds.createVariable("orbit_summary_UTC_start",str,())
        ds.variables["orbit_summary_UTC_start"][()]="2000-01-01T00:00:00Z"


def test_lis_decoder_preserves_raw_timing_quality_and_identity(tmp_path):
    p=tmp_path/"fixture.nc"; _fixture(p)
    decoded=LISProvider.decode(None,p)
    assert decoded["source_sha256"] and decoded["source_file"] == "fixture.nc"
    assert decoded["orbit_start_utc"] == "2000-01-01T00:00:00Z"
    assert decoded["time_encoding"]["utc_conversion"] == "not applied; source UTC orbit start retained separately"
    assert decoded["viewtime"]["TAI93_start"].tolist() == [1.,60.]
    assert decoded["viewtime"]["alert_flag"].tolist() == [0,2]
    assert decoded["events"]["TAI93_time"].tolist() == [42.]


def test_lis_decoder_rejects_missing_coordinates_or_quality(tmp_path):
    p=tmp_path/"bad.nc"; _fixture(p,omit="viewtime_lon")
    with pytest.raises(ValueError,match="lacks required variables"):
        LISProvider.decode(None,p)


def test_lis_decoder_rejects_malformed_netcdf(tmp_path):
    p=tmp_path/"bad.nc"; p.write_bytes(b"not a netcdf")
    with pytest.raises(Exception):
        LISProvider.decode(None,p)
