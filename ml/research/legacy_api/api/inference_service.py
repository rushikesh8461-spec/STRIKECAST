"""
InferenceService: the only thing FastAPI routes talk to for predictions.

Responsible for:
  - turning a validated PredictionRequest into whatever dict shape the model
    loader expects
  - calling the loaded model
  - turning the raw model output into a validated PredictionResponse

No ConvLSTM/model-specific logic lives here - that's the model's job.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from api.config import Settings
from api.model_loader import ModelLoader
from api.schemas import ModelMode, PredictionRequest, PredictionResponse

logger = logging.getLogger("strikecast.inference_service")


class InferenceUnavailableError(Exception):
    """Raised when a prediction is requested but no model is loaded."""


class InferenceService:
    def __init__(self, model_loader: ModelLoader, settings: Settings):
        self._loader = model_loader
        self._settings = settings

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        if not self._loader.ready or self._loader.model is None:
            logger.error("Prediction requested but model is not ready.")
            raise InferenceUnavailableError(
                self._loader.load_error or "Model is not loaded."
            )

        model_input: Dict[str, Any] = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "timestamp": request.timestamp,
            "horizon_minutes": request.horizon_minutes,
            "grid": request.grid,
        }

        logger.info(
            "Running inference: lat=%s lon=%s horizon=%s model_mode=%s",
            request.latitude,
            request.longitude,
            request.horizon_minutes,
            self._settings.model_mode,
        )

        try:
            raw = self._loader.model.predict(model_input)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inference failed.")
            raise

        return PredictionResponse(
            forecast_horizon_minutes=request.horizon_minutes,
            latitude=request.latitude,
            longitude=request.longitude,
            grid_shape=raw.get("grid_shape"),
            prediction=raw["prediction"],
            probability=raw["probability"],
            confidence=raw.get("confidence"),
            model_name=self._loader.model.name,
            model_version=self._loader.model.version,
            model_mode=ModelMode(self._settings.model_mode.lower()),
        )
