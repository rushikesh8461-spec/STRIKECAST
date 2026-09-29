"""
RiskService: orchestrates InferenceService (M3) + risk_engine (mocked M4)
into the stable RiskResponse contract consumed by M6.

FastAPI routes should call this, not inference_service or risk_engine
directly, so responsibilities stay separated (per M5 critical rule #2).
"""
from __future__ import annotations

import logging

from api.inference_service import InferenceService
from api.risk_engine import assess_risk
from api.schemas import RiskRequest, RiskResponse

logger = logging.getLogger("strikecast.risk_service")


class RiskService:
    def __init__(self, inference_service: InferenceService):
        self._inference_service = inference_service

    def assess(self, request: RiskRequest) -> RiskResponse:
        prediction = self._inference_service.predict(request)
        risk_fields = assess_risk(prediction)

        logger.info(
            "Risk assessed: lat=%s lon=%s risk_level=%s",
            request.latitude,
            request.longitude,
            risk_fields["risk_level"].value,
        )

        return RiskResponse(
            forecast=risk_fields["forecast"],
            confidence=risk_fields["confidence"],
            risk_level=risk_fields["risk_level"],
            alerts=risk_fields["alerts"],
            latitude=request.latitude,
            longitude=request.longitude,
            model_version=prediction.model_version,
        )
