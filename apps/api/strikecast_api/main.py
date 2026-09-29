from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import json
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import logging

# M1 -> M4 core package and M5 service boundary.
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env", override=False)
from strikecast_core.data.atmospheric import ingest_atmospheric_data  # noqa: E402
from strikecast_core.data.lightning import get_lightning  # noqa: E402
from strikecast_core.features.point import build_features  # noqa: E402
from strikecast_core.models.inference import TrainedConvLSTM  # noqa: E402
from strikecast_core.risk.engine import RISK_POLICY_VERSION, RISK_THRESHOLDS, assess_risk  # noqa: E402
from strikecast_core.schemas.api import (  # noqa: E402
    LightningResponse, PredictResponse, PredictionRequest, RiskResponse,
)


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MODEL_MODE = os.getenv("STRIKECAST_MODE", "DEMO").strip().upper()
if MODEL_MODE not in {"DEMO", "VALIDATION", "LIVE"}:
    raise RuntimeError("STRIKECAST_MODE must be DEMO, VALIDATION, or LIVE")
logger = logging.getLogger("strikecast.api")
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", "1048576"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_RATE_LIMIT_CLIENTS = int(os.getenv("MAX_RATE_LIMIT_CLIENTS", "4096"))
REQUEST_COUNTS: dict[str, list[float]] = {}

cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
if not CORS_ORIGINS or "*" in CORS_ORIGINS or any(not origin.startswith(("http://localhost", "http://127.0.0.1", "https://")) for origin in CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS must list explicit trusted HTTP(S) origins; wildcard origins are forbidden")

MODEL_LOAD_ERROR = None
if MODEL_MODE == "DEMO":
    model = TrainedConvLSTM()
else:
    registry_dir=Path(os.getenv("STRIKECAST_MODEL_REGISTRY",str(ROOT/"artifacts/models/registry"))).resolve()
    try:
        model=TrainedConvLSTM.from_registry(registry_dir)
    except Exception as exc:
        model=None; MODEL_LOAD_ERROR=f"{type(exc).__name__}: registered model unavailable or incompatible"
        logger.warning("Registered model was not loaded: %s",MODEL_LOAD_ERROR)
MODEL_VERSION = model.version if model else os.getenv("MODEL_VERSION", "unavailable")


class RequestGuardMiddleware:
    """Bound request memory, apply a small per-client limit, and add safe headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        client = scope.get("client")
        client_key = client[0] if client else "unknown"
        now = time.monotonic()
        if client_key not in REQUEST_COUNTS and len(REQUEST_COUNTS) >= MAX_RATE_LIMIT_CLIENTS:
            oldest = min(REQUEST_COUNTS, key=lambda key: max(REQUEST_COUNTS[key], default=0.0))
            REQUEST_COUNTS.pop(oldest, None)
        recent = [t for t in REQUEST_COUNTS.get(client_key, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
        if len(recent) >= RATE_LIMIT_REQUESTS:
            await self._reject(send, 429, "rate_limited", "Too many requests. Try again shortly.", request_id)
            return
        recent.append(now)
        REQUEST_COUNTS[client_key] = recent

        body_parts: list[bytes] = []
        total = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                await self._reject(send, 413, "payload_too_large", "Request body exceeds the configured size limit.", request_id)
                return
            body_parts.append(chunk)
            more = message.get("more_body", False)

        body = b"".join(body_parts)
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        status_code = 500
        response_body = bytearray()

        async def guarded_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-request-id", request_id.encode("ascii")),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                ])
                message["headers"] = headers
            elif message["type"] == "http.response.body" and len(response_body) <= MAX_REQUEST_BYTES:
                response_body.extend(message.get("body", b""))
            await send(message)

        started = time.monotonic()
        await self.app(scope, replay_receive, guarded_send)
        data_status = "not_applicable"
        location_bucket = None
        forecast_horizon = None
        if len(response_body) <= MAX_REQUEST_BYTES:
            try:
                parsed_response = json.loads(response_body)
                if isinstance(parsed_response, dict):
                    data_status = parsed_response.get("data_status", data_status)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        try:
            request_data = json.loads(body) if body else {}
            if isinstance(request_data, dict):
                lat, lon = request_data.get("latitude"), request_data.get("longitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    location_bucket = [round(lat, 1), round(lon, 1)]
                forecast_horizon = request_data.get("horizon_minutes")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        logger.info(json.dumps({
            "event": "request_complete", "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(), "method": scope.get("method"),
            "endpoint": scope.get("path"), "status": status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "model_version": MODEL_VERSION, "model_mode": MODEL_MODE,
            "forecast_horizon_minutes": forecast_horizon, "location_bucket": location_bucket,
            "data_status": data_status,
        }, separators=(",", ":")))

    @staticmethod
    async def _reject(send, status_code: int, error: str, detail: str, request_id: str):
        body = json.dumps({"error": error, "detail": detail, "status_code": status_code}).encode("utf-8")
        await send({"type": "http.response.start", "status": status_code, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii")),
            (b"x-request-id", request_id.encode("ascii")), (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
            (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        ]})
        await send({"type": "http.response.body", "body": body})


app = FastAPI(
    title="StrikeCast Prediction & Risk API",
    version="1.0.0-demo",
    description="M5 service connecting M1 data, M2 features, M3 prediction and M4 calibrated risk intelligence.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "x-request-id"],
)
app.add_middleware(RequestGuardMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "error": "validation_error",
        "detail": "Request fields are invalid. See the API schema.",
        "status_code": 422,
    })


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API exception request_path=%s", request.url.path)
    return JSONResponse(status_code=500, content={
        "error": "internal_error",
        "detail": "An unexpected server error occurred.",
        "status_code": 500,
    })


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(request: PredictionRequest):
    if model is None:
        raise HTTPException(status_code=503, detail={"error": "model_unavailable", "message": "No validated production model is available."})
    timestamp = request.timestamp or "2026-01-01T00:00:00+00:00"
    observations = ingest_atmospheric_data(request.latitude, request.longitude, timestamp, mode="demo")
    feature_batch = build_features(observations)
    prediction = model.predict(feature_batch.sequence)
    risk = assess_risk(prediction.probability, prediction.raw_confidence, request.horizon_minutes)
    return observations, feature_batch, prediction, risk


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model_mode": MODEL_MODE, "model_ready": model is not None}


@app.get("/ready")
def readiness() -> JSONResponse:
    """Service readiness is deliberately distinct from process liveness."""
    ready = model is not None and MODEL_MODE != "DEMO" and getattr(model,"mode",None)=="candidate"
    status = 200 if ready else 503
    return JSONResponse(status_code=status, content={
        "status": "READY" if ready else "BLOCKED",
        "model_mode": "DEMO_ONLY" if MODEL_MODE == "DEMO" else MODEL_MODE,
        "model_version": MODEL_VERSION,
        "scientific_validation_status": "NOT_VALIDATED",
        "production_ready": False,
        "reason": "No accepted real-data model is registered." if not ready else "Scientific production acceptance is not configured.",
        "model_load_error": MODEL_LOAD_ERROR,
    })


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    return {
        "service": "StrikeCast M5 Prediction & Risk API",
        "version": "1.0.0-demo",
        "model_name": model.name if model else "unavailable",
        "model_version": MODEL_VERSION,
        "model_mode": MODEL_MODE,
        "dataset_version": getattr(model,"dataset_version","unavailable") if model else "unavailable",
        "feature_schema_version": getattr(model,"feature_schema_version","unavailable") if model else "unavailable",
        "served_feature_schema_version": getattr(model,"served_feature_schema_version","unavailable") if model else "unavailable",
        "scientific_validation_status": "NOT_VALIDATED",
        "production_ready": False,
        "model_status": "DEMO_ONLY" if MODEL_MODE == "DEMO" else ("CANDIDATE" if model else "INCOMPATIBLE_OR_UNAVAILABLE"),
        "evaluation_status": "NOT_AVAILABLE",
        "risk_threshold_status": "PROVISIONAL_UNVALIDATED",
        "risk_policy_version": RISK_POLICY_VERSION,
        "risk_thresholds": RISK_THRESHOLDS,
        "pipeline": [
            "M1 atmospheric ingestion",
            "M2 feature engineering",
            "M3 ConvLSTM inference adapter",
            "M4 calibration and risk intelligence",
            "M5 API/MLOps service",
            "Lightning observation adapter",
        ],
        "risk_levels": ["LOW", "MODERATE", "HIGH", "SEVERE"],
    }


@app.get("/lightning", response_model=LightningResponse)
def lightning(latitude: float = Query(..., ge=-90, le=90, allow_inf_nan=False), longitude: float = Query(..., ge=-180, le=180, allow_inf_nan=False)) -> LightningResponse:
    try:
        return LightningResponse(**get_lightning(latitude, longitude))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Lightning request failed")
        raise HTTPException(status_code=500, detail={"error": "lightning_error", "message": "Lightning data is unavailable."}) from None


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictionRequest) -> PredictResponse:
    try:
        observations, feature_batch, prediction_result, risk = run_pipeline(request)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Prediction pipeline failed")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "Prediction is temporarily unavailable."}) from None

    grid_shape = None
    if request.grid is not None:
        try:
            grid_shape = [len(request.grid), len(request.grid[0]), len(request.grid[0][0])]
        except (IndexError, TypeError):
            raise HTTPException(status_code=422, detail={"error": "validation_error", "message": "grid must be a rectangular 3D array"})

    return PredictResponse(
        timestamp=observations[-1].timestamp,
        forecast_horizon_minutes=request.horizon_minutes,
        latitude=request.latitude,
        longitude=request.longitude,
        grid_shape=grid_shape,
        prediction=prediction_result.prediction,
        probability=risk.probability,
        confidence=risk.confidence,
        model_name=prediction_result.model_name,
        model_version=MODEL_VERSION,
        model_mode=MODEL_MODE,
        data_source=feature_batch.data_source,
        data_status="LIVE" if feature_batch.data_source.startswith("Open-Meteo live") else "DEMO",
        model_status="DEMO_ONLY" if getattr(model,"mode","demo")=="demo" else "CANDIDATE",
        atmospheric={
            "temperature_c": observations[-1].temperature_c,
            "humidity_pct": observations[-1].humidity_pct,
            "pressure_hpa": observations[-1].pressure_hpa,
            "wind_speed_ms": observations[-1].wind_speed_ms,
            "cape_jkg": observations[-1].cape_jkg,
            "cin_jkg": observations[-1].cin_jkg,
            "precipitation_mm_h": observations[-1].precipitation_mm_h,
        },
    )


@app.post("/risk", response_model=RiskResponse)
def risk(request: PredictionRequest) -> RiskResponse:
    try:
        observations, _, _, assessment = run_pipeline(request)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Risk pipeline failed")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "Risk assessment is temporarily unavailable."}) from None

    return RiskResponse(
        forecast=assessment.forecast,
        probability=assessment.probability,
        calibrated_probability=None,
        confidence=assessment.confidence,
        calibration_status="NOT_VALIDATED",
        risk_level=assessment.risk_level,
        alerts=assessment.alerts,
        timestamp=observations[-1].timestamp,
        latitude=request.latitude,
        longitude=request.longitude,
        model_version=MODEL_VERSION,
        risk_policy_version=RISK_POLICY_VERSION,
        forecast_horizon_minutes=request.horizon_minutes,
    )
