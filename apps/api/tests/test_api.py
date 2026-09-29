from fastapi.testclient import TestClient
import pytest
from strikecast_api.main import app
import strikecast_api.main as api_main

client = TestClient(app)


def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_predict_contract():
    response = client.post('/predict', json={'latitude': 12.9716, 'longitude': 77.5946})
    assert response.status_code == 200
    data = response.json()
    for key in ['timestamp', 'forecast_horizon_minutes', 'latitude', 'longitude', 'grid_shape', 'prediction', 'probability', 'confidence', 'model_name', 'model_version', 'model_mode']:
        assert key in data
    assert 0 <= data['probability'] <= 1
    assert 0 <= data['confidence'] <= 1


def test_risk_contract():
    response = client.post('/risk', json={'latitude': 12.9716, 'longitude': 77.5946, 'horizon_minutes': 60})
    assert response.status_code == 200
    data = response.json()
    assert data['risk_level'] in {'LOW', 'MODERATE', 'HIGH', 'SEVERE'}
    assert isinstance(data['alerts'], list)
    assert data['probability'] == data['calibrated_probability'] or data['calibrated_probability'] is None
    assert data['calibration_status'] == 'NOT_VALIDATED'
    assert data['risk_policy_version'] == 'provisional-1'


def test_invalid_timestamp_is_rejected():
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77, 'timestamp': 'tomorrow'})
    assert response.status_code == 422


def test_timezone_naive_timestamp_is_rejected():
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77, 'timestamp': '2026-09-27T10:00:00'})
    assert response.status_code == 422


@pytest.mark.parametrize('latitude, longitude', [(float('nan'), 77), (float('inf'), 77), (12, float('-inf'))])
def test_non_finite_coordinates_are_rejected(latitude, longitude):
    import json
    response = client.post('/predict', content=json.dumps({'latitude': latitude, 'longitude': longitude}),
                           headers={'content-type': 'application/json'})
    assert response.status_code == 422


def test_model_path_and_url_are_not_request_fields():
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77,
                                            'model_path': 'C:/secret/model.pt',
                                            'model_url': 'https://example.invalid/model.pt'})
    assert response.status_code == 422


def test_ragged_grid_is_rejected():
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77, 'grid': [[[1, 2], [3]]]})
    assert response.status_code == 422


def test_oversized_grid_is_rejected():
    grid = [[[0.0] * 257 for _ in range(256)]]
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77, 'grid': grid})
    assert response.status_code == 422


def test_oversized_http_body_returns_413(monkeypatch):
    monkeypatch.setattr(api_main, 'MAX_REQUEST_BYTES', 32)
    response = client.post('/predict', content=b'{"latitude":12,"longitude":77}' + b' ' * 64,
                          headers={'content-type': 'application/json'})
    assert response.status_code == 413
    assert response.json()['error'] == 'payload_too_large'


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(api_main, 'RATE_LIMIT_REQUESTS', 1)
    monkeypatch.setattr(api_main, 'RATE_LIMIT_WINDOW_SECONDS', 60)
    api_main.REQUEST_COUNTS.clear()
    assert client.get('/health').status_code == 200
    response = client.get('/health')
    assert response.status_code == 429
    api_main.REQUEST_COUNTS.clear()


def test_request_id_security_headers_and_unknown_cors_origin():
    response = client.get('/health', headers={'Origin': 'https://untrusted.invalid'})
    assert response.status_code == 200
    assert response.headers.get('x-request-id')
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert 'access-control-allow-origin' not in response.headers


def test_unavailable_model_returns_503_and_safe_body(monkeypatch):
    monkeypatch.setattr(api_main, 'model', None)
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77})
    assert response.status_code == 503
    assert 'Traceback' not in response.text


def test_prediction_pipeline_failure_returns_generic_500(monkeypatch):
    def fail_pipeline(_request):
        raise RuntimeError('sensitive internal details')

    monkeypatch.setattr(api_main, 'run_pipeline', fail_pipeline)
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77})
    assert response.status_code == 500
    assert response.json()['detail']['message'] == 'Prediction is temporarily unavailable.'
    assert 'sensitive internal details' not in response.text


def test_live_mode_fails_closed_without_validated_model(monkeypatch):
    monkeypatch.setattr(api_main, 'MODEL_MODE', 'LIVE')
    monkeypatch.setattr(api_main, 'model', None)
    response = client.post('/predict', json={'latitude': 12, 'longitude': 77})
    assert response.status_code == 503
    assert response.json()['detail']['error'] == 'model_unavailable'


def test_demo_prediction_is_deterministic():
    payload = {'latitude': 12, 'longitude': 77}
    first = client.post('/predict', json=payload)
    second = client.post('/predict', json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_risk_response_marks_uncalibrated_probability():
    response = client.post('/risk', json={'latitude': 12, 'longitude': 77, 'horizon_minutes': 60})
    assert response.status_code == 200
    body = response.json()
    assert body['calibrated_probability'] is None
    assert body['calibration_status'] == 'NOT_VALIDATED'
    assert body['risk_policy_version'] == 'provisional-1'
    assert body['forecast_horizon_minutes'] == 60


def test_demo_lightning_metadata_is_explicit():
    response = client.get('/lightning', params={'latitude': 12, 'longitude': 77})
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'demo'
    assert body['source_mode'] == 'DEMO'
    assert all(item['source'] == 'StrikeCast presentation simulation' for item in body['strikes'])
