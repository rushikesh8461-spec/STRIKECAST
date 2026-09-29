"""
Minimal MLflow integration for StrikeCast M5.

Goals (per spec): reproducibility + experiment/artifact tracking, without
overcomplicating things or requiring an external cloud service. Defaults to
a local file store (./mlruns) so `mlflow ui` works out of the box.

This module must never crash the API: if MLflow is unavailable or
misconfigured, we log a warning and continue running in mock/no-tracking
mode. Tracking is a supporting concern, not a hard dependency of serving
predictions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from api.config import Settings

logger = logging.getLogger("strikecast.mlflow")

_mlflow_available = True
try:
    import mlflow
except ImportError:  # pragma: no cover
    _mlflow_available = False
    mlflow = None  # type: ignore


def _configure(settings: Settings) -> bool:
    if not settings.mlflow_enabled:
        return False
    if not _mlflow_available:
        logger.warning("mlflow package not installed; skipping MLflow tracking.")
        return False
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to configure MLflow; continuing without tracking.")
        return False


def log_model_load(settings: Settings, model_name: str, model_version: str, ready: bool) -> None:
    """Log a short-lived run recording that a model was loaded at startup."""
    if not _configure(settings):
        return
    try:
        with mlflow.start_run(run_name="model_load"):
            mlflow.log_param("model_name", model_name)
            mlflow.log_param("model_version", model_version)
            mlflow.log_param("model_mode", settings.model_mode)
            mlflow.log_param("app_env", settings.app_env)
            mlflow.log_metric("model_ready", 1.0 if ready else 0.0)
    except Exception:  # noqa: BLE001
        logger.exception("MLflow logging failed for model_load event; continuing without it.")


def log_prediction_event(
    settings: Settings,
    model_version: str,
    metrics: Dict[str, float],
    extra_params: Optional[Dict[str, Any]] = None,
) -> None:
    """Optionally log a lightweight run per prediction/risk call.

    Kept intentionally cheap - this is meant for local dev/demo traceability,
    not high-throughput production telemetry.
    """
    if not _configure(settings):
        return
    try:
        with mlflow.start_run(run_name="inference"):
            mlflow.log_param("model_version", model_version)
            for key, value in (extra_params or {}).items():
                mlflow.log_param(key, value)
            for key, value in metrics.items():
                mlflow.log_metric(key, value)
    except Exception:  # noqa: BLE001
        logger.exception("MLflow logging failed for inference event; continuing without it.")
