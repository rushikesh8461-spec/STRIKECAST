from __future__ import annotations


def test_predict_valid_request(client, valid_prediction_payload):
    resp = client.post("/predict", json=valid_prediction_payload)
    assert resp.status_code == 200
    body = resp.json()
    for key in [
        "timestamp",
        "forecast_horizon_minutes",
        "latitude",
        "longitude",
        "prediction",
        "probability",
        "model_name",
        "model_version",
        "model_mode",
    ]:
        assert key in body
    assert 0.0 <= body["probability"] <= 1.0
    assert body["model_mode"] == "mock"


def test_predict_is_deterministic(client, valid_prediction_payload):
    resp1 = client.post("/predict", json=valid_prediction_payload)
    resp2 = client.post("/predict", json=valid_prediction_payload)
    b1, b2 = resp1.json(), resp2.json()
    assert b1["prediction"] == b2["prediction"]
    assert b1["probability"] == b2["probability"]


def test_predict_invalid_latitude(client):
    payload = {"latitude": 999, "longitude": 77.5, "horizon_minutes": 60}
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation_error"
    assert "detail" in body


def test_predict_missing_required_field(client):
    resp = client.post("/predict", json={"longitude": 77.5})
    assert resp.status_code == 422


def test_predict_invalid_timestamp(client):
    payload = {"latitude": 12.9, "longitude": 77.5, "timestamp": "not-a-date"}
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 422


def test_predict_with_grid(client):
    payload = {
        "latitude": 12.9,
        "longitude": 77.5,
        "horizon_minutes": 30,
        "grid": [[[1.0, 2.0], [3.0, 4.0]]],
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 200
    assert resp.json()["grid_shape"] == [1, 2, 2]
