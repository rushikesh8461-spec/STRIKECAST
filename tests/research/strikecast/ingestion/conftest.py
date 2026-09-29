import pytest

from src.ingestion.config import load_config


@pytest.fixture(scope="session")
def config():
    return load_config()
