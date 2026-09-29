#!/usr/bin/env python3
"""
Run the StrikeCast M5 API locally.

Usage:
    python scripts/run_api.py

Configuration is read entirely from environment variables (see .env.example).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the project root is importable when run as `python scripts/run_api.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from api.config import get_settings


def main() -> None:
    settings = get_settings()
    reload_enabled = settings.app_env.lower() in {"development", "dev", "local"}
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
