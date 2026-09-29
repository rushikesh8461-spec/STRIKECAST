"""
Configuration loading for the ingestion module.

Rules (Phase 8):
- No hard-coded file paths, API keys, dataset locations, URLs, or credentials
  anywhere in source files.
- All of that lives in config/ingestion_config.yaml (paths/grids/thresholds,
  safe to commit) and environment variables (secrets, via .env — NOT
  committed; see .env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The only hard-coded path we allow: where to look for the config file
# itself, resolved relative to the repository root, with an env override.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "research" / "ingestion_config.yaml"


@dataclass
class IngestionConfig:
    raw: dict

    @property
    def data_root(self) -> Path:
        # See src/preprocessing/config.py's data_root for the rationale:
        # paths.data_root ("data") is relative-by-convention, and must be
        # anchored to the repo root, not whatever directory the caller's
        # shell happens to be in, or M3 entrypoints break when run from
        # outside the repo root.
        raw_path = Path(self.raw["paths"]["data_root"]).expanduser()
        if raw_path.is_absolute():
            return raw_path.resolve()
        return (_REPO_ROOT / raw_path).resolve()

    @property
    def raw_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["raw_subdir"]

    @property
    def interim_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["interim_subdir"]

    @property
    def sample_demo_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["sample_demo_subdir"]

    def source_dir(self, source: str, demo: bool = False) -> Path:
        base = self.sample_demo_dir if demo else self.raw_dir
        return base / source

    def grid_spec_dict(self) -> dict:
        return self.raw["grid"]

    def quality_thresholds(self) -> dict:
        return self.raw["quality_thresholds"]

    def demo_dataset_params(self) -> dict:
        return self.raw["sample_demo"]

    def get_secret(self, env_var_name: str) -> str | None:
        """Secrets are NEVER read from the yaml config — only from the
        environment, so nothing sensitive is ever committed to the repo."""
        return os.environ.get(env_var_name)


def load_config(path: str | Path | None = None) -> IngestionConfig:
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(
            f"Ingestion config not found at {config_path}. "
            "Copy config/ingestion_config.example.yaml if it is missing, "
            "or pass an explicit path to load_config()."
        )
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    return IngestionConfig(raw=raw)
