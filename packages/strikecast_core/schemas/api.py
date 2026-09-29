"""Canonical request and response schemas for the served API."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timestamp: str | None = None
    horizon_minutes: int = Field(default=60, ge=5, le=360)
    grid: list[list[list[Any]]] | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("grid")
    @classmethod
    def validate_grid(cls, value: list[list[list[Any]]] | None):
        if value is None:
            return value
        if not value or not value[0] or not value[0][0]:
            raise ValueError("grid must be a non-empty rectangular 3D array")
        rows, cols = len(value[0]), len(value[0][0])
        if len(value) * rows * cols > 65536:
            raise ValueError("grid exceeds the 65536-value limit")
        if any(len(frame) != rows or any(len(row) != cols for row in frame) for frame in value):
            raise ValueError("grid must be rectangular")
        try:
            if any(not math.isfinite(float(item)) for frame in value for row in frame for item in row):
                raise ValueError("grid values must be finite numbers")
        except (TypeError, ValueError) as exc:
            raise ValueError("grid values must be finite numbers") from exc
        return value


class PredictResponse(BaseModel):
    timestamp: str
    forecast_horizon_minutes: int
    latitude: float
    longitude: float
    grid_shape: list[int] | None
    prediction: float
    probability: float
    confidence: float
    model_name: str
    model_version: str
    model_mode: str
    data_source: str
    data_status: str
    model_status: str
    atmospheric: dict[str, float]


class LightningStrike(BaseModel):
    latitude: float
    longitude: float
    timestamp: str
    age_minutes: int | float | None = None
    polarity: int | None = None
    intensity: float | None = None
    source: str | None = None
    quality: float | None = Field(default=None, ge=0, le=1)


class LightningResponse(BaseModel):
    mode: str
    source_mode: str
    source: str
    updated_at: str
    strikes: list[LightningStrike]


class RiskResponse(BaseModel):
    forecast: str
    probability: float
    calibrated_probability: float | None
    confidence: float
    calibration_status: str
    risk_level: str
    alerts: list[str]
    timestamp: str
    latitude: float
    longitude: float
    model_version: str
    risk_policy_version: str
    forecast_horizon_minutes: int
