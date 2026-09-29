#!/usr/bin/env python
"""Exercise the canonical M5 API boundary in-process."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "apps/api")]
os.environ.setdefault("STRIKECAST_MODE", "DEMO")

from fastapi.testclient import TestClient  # noqa: E402
import strikecast_api.main as api  # noqa: E402


def main() -> int:
    client = TestClient(api.app)
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 503 and ready.json()["production_ready"] is False
    metadata = client.get("/metadata")
    assert metadata.status_code == 200 and metadata.json()["model_mode"] == "DEMO"
    assert metadata.json()["scientific_validation_status"] == "NOT_VALIDATED"
    assert metadata.json()["production_ready"] is False
    request = {"latitude": 12.9716, "longitude": 77.5946}
    first = client.post("/predict", json=request)
    second = client.post("/predict", json=request)
    assert first.status_code == 200 and first.json() == second.json()
    assert first.json()["data_status"] == "DEMO" and first.json()["model_status"] == "DEMO_ONLY"
    risk = client.post("/risk", json=request)
    assert risk.status_code == 200 and risk.json()["calibration_status"] == "NOT_VALIDATED"
    lightning = client.get("/lightning", params=request)
    assert lightning.status_code == 200 and lightning.json()["mode"] == "demo"

    mode, model = api.MODEL_MODE, api.model
    try:
        api.MODEL_MODE, api.model = "LIVE", None
        refused = client.post("/predict", json=request)
        assert refused.status_code == 503
    finally:
        api.MODEL_MODE, api.model = mode, model
    print("Smoke test passed: health, readiness, metadata, predict, risk, lightning, deterministic DEMO, LIVE fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
