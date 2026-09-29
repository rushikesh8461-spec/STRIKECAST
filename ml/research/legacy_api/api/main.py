"""
StrikeCast M5 FastAPI application.

Endpoints:
  GET  /health    - liveness + model-readiness
  POST /predict   - run model inference (M3 abstraction)
  POST /risk      - risk-aware prediction (M3 + mocked M4)
  GET  /metadata  - service/model metadata

Routes are intentionally thin: all logic lives in the service layer
(inference_service.py, risk_service.py) and the model abstraction
(model_loader.py). No ConvLSTM/model internals here.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import Settings, get_settings
from api.dependencies import get_inference_service, get_risk_service
from api.inference_service import InferenceService, InferenceUnavailableError
from api.logging_config import setup_logging
from api.model_loader import ModelLoader
from api.risk_service import RiskService
from api.schemas import (
    ErrorResponse,
    HealthResponse,
    MetadataResponse,
    ModelMode,
    PredictionRequest,
    PredictionResponse,
    RiskRequest,
    RiskResponse,
)
from mlops.mlflow.tracking import log_model_load

logger = logging.getLogger("strikecast.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting StrikeCast M5 API (env=%s, model_mode=%s)", settings.app_env, settings.model_mode)

    model_loader = ModelLoader(settings)
    model_loader.load()

    app.state.settings = settings
    app.state.model_loader = model_loader
    app.state.inference_service = InferenceService(model_loader, settings)
    app.state.risk_service = RiskService(app.state.inference_service)

    model_name = model_loader.model.name if model_loader.model else "unknown"
    model_version = model_loader.model.version if model_loader.model else settings.model_version
    log_model_load(settings, model_name, model_version, model_loader.ready)

    yield

    logger.info("Shutting down StrikeCast M5 API.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="StrikeCast M5 API",
        description="Backend, API & MLOps layer for the StrikeCast nowcasting system.",
        version=settings.service_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    register_routes(app)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="validation_error",
                detail="One or more fields failed validation. See request schema.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ).model_dump(),
        )

    @app.exception_handler(InferenceUnavailableError)
    async def inference_unavailable_handler(request: Request, exc: InferenceUnavailableError):
        logger.error("Inference unavailable on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="model_unavailable",
                detail="The prediction model is not ready. Check /health for details.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Never leak stack traces or internal exception messages to the client.
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred. Please try again later.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ).model_dump(),
        )


def register_routes(app: FastAPI) -> None:
    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health(request: Request, settings: Settings = Depends(get_settings)):
        model_loader: ModelLoader = request.app.state.model_loader
        return HealthResponse(
            status="alive",
            model_ready=model_loader.ready,
            model_mode=ModelMode(settings.model_mode.lower()),
            app_env=settings.app_env,
        )

    @app.get("/metadata", response_model=MetadataResponse, tags=["system"])
    async def metadata(request: Request, settings: Settings = Depends(get_settings)):
        model_loader: ModelLoader = request.app.state.model_loader
        model = model_loader.model
        return MetadataResponse(
            service_name=settings.service_name,
            service_version=settings.service_version,
            app_env=settings.app_env,
            model_mode=ModelMode(settings.model_mode.lower()),
            model_name=model.name if model else settings.model_name,
            model_version=model.version if model else settings.model_version,
            model_ready=model_loader.ready,
            mlflow_tracking_uri=settings.mlflow_tracking_uri,
        )

    @app.post(
        "/predict",
        response_model=PredictionResponse,
        responses={503: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
        tags=["inference"],
    )
    async def predict(
        payload: PredictionRequest,
        inference_service: InferenceService = Depends(get_inference_service),
    ):
        return inference_service.predict(payload)

    @app.post(
        "/risk",
        response_model=RiskResponse,
        responses={503: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
        tags=["risk"],
    )
    async def risk(
        payload: RiskRequest,
        risk_service: RiskService = Depends(get_risk_service),
    ):
        return risk_service.assess(payload)


app = create_app()
