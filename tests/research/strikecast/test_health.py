from __future__ import annotations


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_schema(client):
    resp = client.get("/health")
    body = resp.json()
    assert body["status"] == "alive"
    assert body["model_ready"] is True  # mock model always loads successfully
    assert body["model_mode"] == "mock"
    assert "timestamp" in body
    assert "app_env" in body
