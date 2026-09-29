"""
Pydantic schemas for the StrikeCast M5 API.

These are the STABLE contract between M5 (backend) and M6 (frontend), and the
expected shape of what M3 (model) / M4 (risk) conceptually provide. Mock and
real model modes must both produce responses that validate against these
exact schemas - that's what lets M6 build against the API before M3/M4 are
finished.

Do not change field names/types casually; M6 depends on this file's shape.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------
class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class ModelMode(str, Enum):
    MOCK = "mock"
    REAL = "real"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., description="'alive' if the service process is running.")
    model_ready: bool = Field(..., description="True only if the model loaded successfully.")
    model_mode: ModelMode
    app_env: str
    timestamp: str = Field(default_factory=_utc_now_iso)


# ---------------------------------------------------------------------------
# /metadata
# ---------------------------------------------------------------------------
class MetadataResponse(BaseModel):
    service_name: str
    service_version: str
    app_env: str
    model_mode: ModelMode
    model_name: str
    model_version: str
    model_ready: bool
    mlflow_tracking_uri: str
    supported_endpoints: List[str] = Field(
        default_factory=lambda: ["/health", "/predict", "/risk", "/metadata"]
    )


# ---------------------------------------------------------------------------
# /predict
# ---------------------------------------------------------------------------
class PredictionRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude of the query point.")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of the query point.")
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp for the observation window. Defaults to now (UTC).",
    )
    horizon_minutes: int = Field(
        default=60, ge=5, le=360, description="How far ahead (minutes) to forecast."
    )
    grid: Optional[List[List[List[float]]]] = Field(
        default=None,
        description=(
            "Optional spatio-temporal input frames [time][row][col] produced by M2. "
            "Ignored in mock mode; consumed by the real ConvLSTM checkpoint."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be a valid ISO-8601 string") from exc
        return v

    @field_validator("grid")
    @classmethod
    def _validate_grid(cls, v):
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("grid, if provided, must contain at least one time frame")
        return v


class PredictionResponse(BaseModel):
    timestamp: str = Field(default_factory=_utc_now_iso)
    forecast_horizon_minutes: int
    latitude: float
    longitude: float
    grid_shape: Optional[List[int]] = Field(
        default=None, description="[time, rows, cols] of the input grid, if one was supplied."
    )
    prediction: float = Field(..., description="Primary model output, e.g. predicted intensity.")
    probability: float = Field(..., ge=0.0, le=1.0, description="Probability of the event occurring.")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    model_name: str
    model_version: str
    model_mode: ModelMode


# ---------------------------------------------------------------------------
# /risk
# ---------------------------------------------------------------------------
class RiskRequest(PredictionRequest):
    """Risk requests need the same inputs as prediction; M5 runs inference
    internally and passes the result through the (mocked) M4 risk engine."""


class RiskResponse(BaseModel):
    forecast: str = Field(..., description="Human-readable forecast summary.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    alerts: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=_utc_now_iso)
    # Extra traceability fields (additive - safe for M6 to ignore).
    latitude: float
    longitude: float
    model_version: str


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Short machine-friendly error code.")
    detail: str = Field(..., description="Human-readable explanation. Never a raw stack trace.")
    status_code: int
