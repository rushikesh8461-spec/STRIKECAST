from __future__ import annotations


def test_metadata_schema(client):
    resp = client.get("/metadata")
    assert resp.status_code == 200
    body = resp.json()
    for key in [
        "service_name",
        "service_version",
        "app_env",
        "model_mode",
        "model_name",
        "model_version",
        "model_ready",
        "mlflow_tracking_uri",
        "supported_endpoints",
    ]:
        assert key in body
    assert body["model_ready"] is True
    assert set(body["supported_endpoints"]) == {"/health", "/predict", "/risk", "/metadata"}
