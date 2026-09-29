from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import ErrorResponse, PredictionRequest, RiskLevel, RiskResponse


def test_prediction_request_valid():
    req = PredictionRequest(latitude=10.0, longitude=20.0, horizon_minutes=30)
    assert req.horizon_minutes == 30


def test_prediction_request_rejects_out_of_range_latitude():
    with pytest.raises(ValidationError):
        PredictionRequest(latitude=200.0, longitude=20.0)


def test_prediction_request_rejects_out_of_range_horizon():
    with pytest.raises(ValidationError):
        PredictionRequest(latitude=10.0, longitude=20.0, horizon_minutes=1)


def test_prediction_request_rejects_empty_grid():
    with pytest.raises(ValidationError):
        PredictionRequest(latitude=10.0, longitude=20.0, grid=[])


def test_risk_response_requires_valid_enum():
    resp = RiskResponse(
        forecast="test",
        confidence=0.5,
        risk_level=RiskLevel.HIGH,
        alerts=["test alert"],
        latitude=1.0,
        longitude=2.0,
        model_version="1.0.0",
    )
    assert resp.risk_level == RiskLevel.HIGH

    with pytest.raises(ValidationError):
        RiskResponse(
            forecast="test",
            confidence=0.5,
            risk_level="NOT_A_LEVEL",
            alerts=[],
            latitude=1.0,
            longitude=2.0,
            model_version="1.0.0",
        )


def test_error_response_shape():
    err = ErrorResponse(error="validation_error", detail="bad input", status_code=422)
    assert err.status_code == 422
