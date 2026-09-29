import pytest

from src.ingestion.demo_generator import generate_all
from src.ingestion.config import load_config as load_ingestion_config
from src.preprocessing.config import load_config as load_preprocessing_config


@pytest.fixture(scope="session")
def preprocessing_config():
    return load_preprocessing_config()


@pytest.fixture(scope="session", autouse=True)
def ensure_m1_demo_data():
    """The M2 tests read the M1 manifest, so make sure it (and the demo
    .npz/.json files it points to) exists before any test runs — this
    keeps tests/preprocessing/ independently runnable without requiring
    tests/ingestion/ to have run first, and never requires live external
    data (spec Phase 14)."""
    generate_all(load_ingestion_config())
