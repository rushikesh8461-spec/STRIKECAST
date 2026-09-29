#!/usr/bin/env python3
"""
Start a local MLflow UI server pointed at the project's local tracking store.

Usage:
    python scripts/run_mlflow.py

Then open http://127.0.0.1:5000 to browse experiments/runs.
Requires MLflow to be installed (see requirements.txt) - no cloud service
or external database is required for local development.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.config import get_settings


def main() -> None:
    settings = get_settings()
    tracking_uri = settings.mlflow_tracking_uri
    print(f"Starting MLflow UI for tracking URI: {tracking_uri}")
    subprocess.run(
        [
            "mlflow",
            "ui",
            "--backend-store-uri",
            tracking_uri,
            "--host",
            "127.0.0.1",
            "--port",
            "5000",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
