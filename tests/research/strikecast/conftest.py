from __future__ import annotations

import os

import pytest

# Force deterministic, dependency-free settings BEFORE any api.* module is
# imported, since Settings/get_settings are read at import/startup time.
os.environ["MODEL_MODE"] = "mock"
os.environ["APP_ENV"] = "test"
os.environ["MLFLOW_TRACKING_URI"] = "file:./mlruns-test"
os.environ["MLFLOW_ENABLED"] = "false"  # keep tests hermetic/fast, no filesystem writes needed
os.environ["MODEL_VERSION"] = "0.0.0-test"

from fastapi.testclient import TestClient  # noqa: E402

from api.config import get_settings  # noqa: E402
from api.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def valid_prediction_payload():
    return {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "horizon_minutes": 60,
    }
