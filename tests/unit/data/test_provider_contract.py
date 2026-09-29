from __future__ import annotations

import json

import pytest

from strikecast_core.data import atmospheric as ingestion
from strikecast_core.data import lightning as lightning_ingestion


def test_demo_atmosphere_is_deterministic_and_timezone_aware():
    first = ingestion.ingest_atmospheric_data(12.0, 77.0, mode="demo")
    second = ingestion.ingest_atmospheric_data(12.0, 77.0, mode="demo")
    assert first == second
    assert first[0].timestamp.endswith("+00:00")
    assert first[-1].source == "synthetic-fallback"


def test_live_provider_failure_does_not_silently_fallback(monkeypatch):
    def fail(_latitude, _longitude):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ingestion, "_fetch_live", fail)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        ingestion.ingest_atmospheric_data(12.0, 77.0, mode="live")


def test_unknown_atmospheric_mode_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        ingestion.ingest_atmospheric_data(12.0, 77.0, mode="automatic")


def test_live_lightning_without_provider_is_unavailable_not_demo(monkeypatch):
    monkeypatch.setenv("LIGHTNING_MODE", "live")
    monkeypatch.delenv("LIGHTNING_FEED_URL", raising=False)
    result = lightning_ingestion.get_lightning(12.0, 77.0)
    assert result["mode"] == "none"
    assert result["source_mode"] == "UNAVAILABLE"
    assert result["strikes"] == []


def test_live_lightning_rejects_bad_timestamp_coordinates_and_age(monkeypatch):
    monkeypatch.setenv("LIGHTNING_MODE", "live")
    monkeypatch.setenv("LIGHTNING_FEED_URL", "https://feed.example/strikes")
    monkeypatch.setenv("LIGHTNING_FEED_ALLOWED_HOSTS", "feed.example")
    payload = [
        {"latitude": 91, "longitude": 77, "timestamp": "2026-01-01T00:00:00Z"},
        {"latitude": 12, "longitude": 77, "timestamp": "yesterday"},
        {"latitude": 12, "longitude": 77, "timestamp": "2026-01-01T00:00:00Z", "age_minutes": -1},
    ]

    class Response:
        status_code = 200
        headers = {"content-type": "application/json", "content-length": str(len(json.dumps(payload)))}

        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def raise_for_status(self): return None
        def iter_bytes(self): yield json.dumps(payload).encode()

    class Client:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def stream(self, *_args, **_kwargs): return Response()

    monkeypatch.setattr(lightning_ingestion.httpx, "Client", Client)
    result = lightning_ingestion.get_lightning(12, 77)
    assert result["mode"] == "live"
    assert result["strikes"] == []
