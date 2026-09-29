import pytest

from src.ingestion.config import load_config
from src.ingestion.sources import SatelliteDataSource


def test_missing_config_file_raises_clear_error():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/to/config.yaml")


def test_real_source_mode_raises_not_implemented_not_silent_mock(config):
    """A caller who forgets demo=True must get a loud, explicit error —
    never silently receive synthetic data labeled as real."""
    adapter = SatelliteDataSource(config=config, demo=False)
    with pytest.raises(NotImplementedError):
        adapter.get_record()


def test_lightning_handles_zero_strike_window(config):
    """If a timestep genuinely has zero strikes, validation must not crash —
    it should report an empty-but-valid window rather than dividing by zero."""
    from src.ingestion.sources.lightning import LightningDataSource

    adapter = LightningDataSource(config=config, demo=True)
    raw = {"timestamps": ["2026-06-01T00:00:00Z"], "points": []}
    report = adapter.validate(raw)
    assert report is not None
    assert report.missing_fraction == 0.0
