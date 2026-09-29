import pytest

from src.ingestion.sources import (
    SatelliteDataSource,
    LightningDataSource,
    NWPDataSource,
    RadarDataSource,
)

ALL_GRIDDED_SOURCES = [SatelliteDataSource, NWPDataSource, RadarDataSource]
ALL_SOURCES = ALL_GRIDDED_SOURCES + [LightningDataSource]


@pytest.mark.parametrize("source_cls", ALL_GRIDDED_SOURCES)
def test_gridded_source_load_shape(config, source_cls):
    adapter = source_cls(config=config, demo=True)
    raw = adapter.load()
    n_t = len(raw["timestamps"])
    assert raw["data"].shape[0] == n_t
    assert raw["data"].shape[1] == raw["grid"].n_lat
    assert raw["data"].shape[2] == raw["grid"].n_lon
    assert raw["data"].shape[3] == len(adapter.get_schema())


def test_lightning_load_returns_points(config):
    adapter = LightningDataSource(config=config, demo=True)
    raw = adapter.load()
    assert len(raw["timestamps"]) == config.demo_dataset_params()["n_timestamps"]
    assert isinstance(raw["points"], list)
    assert len(raw["points"]) > 0
    for p in raw["points"][:5]:
        assert "latitude" in p and "longitude" in p and "timestamp" in p


@pytest.mark.parametrize("source_cls", ALL_SOURCES)
def test_non_demo_raises_not_implemented(config, source_cls):
    """Real (non-demo) acquisition is explicitly not implemented in this
    repository — adapters must say so clearly rather than silently return
    synthetic data under a real-data label."""
    adapter = source_cls(config=config, demo=False)
    with pytest.raises(NotImplementedError):
        adapter.load()


@pytest.mark.parametrize("source_cls", ALL_SOURCES)
def test_get_record_end_to_end(config, source_cls):
    adapter = source_cls(config=config, demo=True)
    record = adapter.get_record()
    assert record.quality is not None
    assert record.provenance["is_synthetic"] is True
    assert len(record.timestamps) == config.demo_dataset_params()["n_timestamps"]
