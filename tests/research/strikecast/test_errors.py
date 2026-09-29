from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import get_inference_service
from api.main import create_app


def test_unknown_route_returns_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404


def test_wrong_method_returns_405(client):
    resp = client.get("/predict")
    assert resp.status_code == 405


def test_service_unavailable_response_has_no_stack_trace(monkeypatch):
    """Simulate the model failing to load and verify /predict responds with a
    clean structured error, never a raw traceback."""
    app = create_app()

    class _AlwaysUnavailable:
        def predict(self, request):
            from api.inference_service import InferenceUnavailableError

            raise InferenceUnavailableError("model not ready")

    app.dependency_overrides[get_inference_service] = lambda: _AlwaysUnavailable()

    with TestClient(app) as test_client:
        resp = test_client.post(
            "/predict",
            json={"latitude": 1.0, "longitude": 1.0, "horizon_minutes": 30},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"] == "model_unavailable"
        assert "Traceback" not in body["detail"]
        assert "model not ready" not in body["detail"]  # internal detail not leaked verbatim
