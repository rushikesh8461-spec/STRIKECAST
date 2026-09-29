from __future__ import annotations


def test_risk_valid_request(client, valid_prediction_payload):
    resp = client.post("/risk", json=valid_prediction_payload)
    assert resp.status_code == 200
    body = resp.json()
    for key in ["forecast", "confidence", "risk_level", "alerts", "timestamp", "latitude", "longitude", "model_version"]:
        assert key in body
    assert body["risk_level"] in {"LOW", "MODERATE", "HIGH", "SEVERE"}
    assert isinstance(body["alerts"], list)


def test_risk_invalid_input(client):
    resp = client.post("/risk", json={"latitude": "not-a-number", "longitude": 77.5})
    assert resp.status_code == 422


def test_risk_low_probability_has_no_alerts(client):
    # Use coordinates whose deterministic mock hash lands in the LOW bucket.
    # We can't guarantee the bucket without running the hash, so instead we
    # assert the *contract*: LOW risk always has an empty alerts list.
    resp = client.post("/risk", json={"latitude": 0.0, "longitude": 0.0, "horizon_minutes": 60})
    body = resp.json()
    if body["risk_level"] == "LOW":
        assert body["alerts"] == []
    else:
        assert len(body["alerts"]) > 0
