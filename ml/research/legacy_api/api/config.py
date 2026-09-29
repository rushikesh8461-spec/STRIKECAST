"""
Environment-based configuration for the StrikeCast M5 backend.

No secrets or paths are hard-coded here. Everything is read from environment
variables (optionally loaded from a local .env file for development), with
safe defaults for local/mock development only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

try:
    # Optional: only used for local development convenience.
    # If python-dotenv isn't installed, the app still works using real env vars.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - trivial fallback
    pass


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: List[str]) -> List[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Model / inference configuration.
    model_mode: str = field(default_factory=lambda: os.getenv("MODEL_MODE", "mock"))
    model_path: str = field(default_factory=lambda: os.getenv("MODEL_PATH", ""))
    model_registry_dir: str = field(default_factory=lambda: os.getenv("MODEL_REGISTRY_DIR", "./models/registry"))
    model_checksum: str = field(default_factory=lambda: os.getenv("MODEL_SHA256", ""))
    model_version: str = field(default_factory=lambda: os.getenv("MODEL_VERSION", "0.0.0-mock"))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "strikecast-convlstm"))

    # MLflow.
    mlflow_tracking_uri: str = field(
        default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
    )
    mlflow_experiment_name: str = field(
        default_factory=lambda: os.getenv("MLFLOW_EXPERIMENT_NAME", "strikecast-m5")
    )
    mlflow_enabled: bool = field(default_factory=lambda: _get_bool("MLFLOW_ENABLED", True))

    # Logging.
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # CORS - restrict in production via CORS_ORIGINS env var (comma separated).
    cors_origins: List[str] = field(
        default_factory=lambda: _get_list("CORS_ORIGINS", ["http://localhost:3000"])
    )

    service_name: str = "strikecast-m5-api"
    service_version: str = field(default_factory=lambda: os.getenv("SERVICE_VERSION", "0.1.0"))

    @property
    def is_mock_mode(self) -> bool:
        return self.model_mode.strip().lower() == "mock"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Re-reads env only once per process."""
    return Settings()
