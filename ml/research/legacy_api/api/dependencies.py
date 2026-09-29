"""
FastAPI dependency providers.

Services are created once at app startup (see main.py's lifespan handler)
and stored on `app.state`. These dependency functions just fetch them back
out for route handlers, so routes stay thin and testable.
"""
from __future__ import annotations

from fastapi import Request

from api.config import Settings, get_settings
from api.inference_service import InferenceService
from api.model_loader import ModelLoader
from api.risk_service import RiskService


def get_app_settings() -> Settings:
    return get_settings()


def get_model_loader(request: Request) -> ModelLoader:
    return request.app.state.model_loader


def get_inference_service(request: Request) -> InferenceService:
    return request.app.state.inference_service


def get_risk_service(request: Request) -> RiskService:
    return request.app.state.risk_service
