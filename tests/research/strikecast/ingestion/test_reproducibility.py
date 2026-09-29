import numpy as np

from src.ingestion.sources import SatelliteDataSource, LightningDataSource, NWPDataSource, RadarDataSource


def test_satellite_load_is_deterministic(config):
    a = SatelliteDataSource(config=config, demo=True)
    b = SatelliteDataSource(config=config, demo=True)
    raw_a = a.load()
    raw_b = b.load()
    assert np.array_equal(raw_a["data"], raw_b["data"], equal_nan=True)
    assert raw_a["timestamps"] == raw_b["timestamps"]


def test_nwp_load_is_deterministic(config):
    raw_a = NWPDataSource(config=config, demo=True).load()
    raw_b = NWPDataSource(config=config, demo=True).load()
    assert np.array_equal(raw_a["data"], raw_b["data"], equal_nan=True)


def test_radar_load_is_deterministic(config):
    raw_a = RadarDataSource(config=config, demo=True).load()
    raw_b = RadarDataSource(config=config, demo=True).load()
    assert np.array_equal(raw_a["data"], raw_b["data"], equal_nan=True)


def test_lightning_load_is_deterministic(config):
    raw_a = LightningDataSource(config=config, demo=True).load()
    raw_b = LightningDataSource(config=config, demo=True).load()
    assert len(raw_a["points"]) == len(raw_b["points"])
    for pa, pb in zip(raw_a["points"], raw_b["points"]):
        assert pa == pb
