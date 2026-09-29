"""
Risk engine: conceptually the M4 interface, mocked here so M5 can be built
and tested end-to-end before M4 is finished.

This module is intentionally pure and stateless: given a prediction, return
risk fields. When the real M4 risk-intelligence module is ready, this file
is the one place that needs to change - `risk_service.py` and the FastAPI
routes should not need to change at all.

Real M4 integration point:
    from m4.risk_intelligence import assess_risk
    return assess_risk(prediction)
"""
from __future__ import annotations

from typing import List

from api.schemas import PredictionResponse, RiskLevel

# Thresholds are placeholders for the mock engine only - M4 owns the real
# calibrated thresholds.
_LOW_MAX = 0.25
_MODERATE_MAX = 0.5
_HIGH_MAX = 0.75


def classify_risk_level(probability: float) -> RiskLevel:
    if probability < _LOW_MAX:
        return RiskLevel.LOW
    if probability < _MODERATE_MAX:
        return RiskLevel.MODERATE
    if probability < _HIGH_MAX:
        return RiskLevel.HIGH
    return RiskLevel.SEVERE


def build_alerts(risk_level: RiskLevel, horizon_minutes: int) -> List[str]:
    if risk_level == RiskLevel.LOW:
        return []
    if risk_level == RiskLevel.MODERATE:
        return [f"Conditions may develop within {horizon_minutes} minutes; monitor updates."]
    if risk_level == RiskLevel.HIGH:
        return [
            f"Elevated risk expected within {horizon_minutes} minutes.",
            "Consider precautionary measures for outdoor activity.",
        ]
    # SEVERE
    return [
        f"Severe risk expected within {horizon_minutes} minutes.",
        "Take immediate precautionary action.",
        "Monitor official alerts for updates.",
    ]


def build_forecast_summary(prediction: PredictionResponse, risk_level: RiskLevel) -> str:
    return (
        f"{risk_level.value.title()} risk forecast for the next "
        f"{prediction.forecast_horizon_minutes} minutes "
        f"(probability={prediction.probability:.2f})."
    )


def assess_risk(prediction: PredictionResponse) -> dict:
    """Mocked M4 risk assessment. Deterministic given a PredictionResponse."""
    risk_level = classify_risk_level(prediction.probability)
    return {
        "forecast": build_forecast_summary(prediction, risk_level),
        "confidence": prediction.confidence if prediction.confidence is not None else prediction.probability,
        "risk_level": risk_level,
        "alerts": build_alerts(risk_level, prediction.forecast_horizon_minutes),
    }
