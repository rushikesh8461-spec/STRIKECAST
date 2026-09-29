"""
Configuration loading for the M2 preprocessing/features module.

Mirrors src/ingestion/config.py's conventions (Phase 8 rule, restated for
M2): no hard-coded file paths, thresholds, or dataset locations anywhere in
source files. Everything lives in config/preprocessing_config.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "research" / "preprocessing_config.yaml"


@dataclass
class PreprocessingConfig:
    raw: dict

    # --- paths ---
    @property
    def data_root(self) -> Path:
        # config/preprocessing_config.yaml's paths.data_root is documented
        # as "data" (a relative path). A bare .resolve() would previously
        # resolve that against the *current working directory*, so
        # `build_dataset()` silently broke unless invoked from the repo
        # root (M2<->M3 integration bug: M3's train.py/predict.py are run
        # from wherever the caller's shell happens to be). An explicit
        # absolute path in the config is still honored as-is; a relative
        # one is anchored to the repository root instead of cwd.
        raw_path = Path(self.raw["paths"]["data_root"]).expanduser()
        if raw_path.is_absolute():
            return raw_path.resolve()
        return (_REPO_ROOT / raw_path).resolve()

    @property
    def sample_demo_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["sample_demo_subdir"]

    @property
    def raw_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["raw_subdir"]

    @property
    def processed_dir(self) -> Path:
        return self.data_root / self.raw["paths"]["processed_subdir"]

    # --- temporal alignment ---
    def temporal_alignment_cfg(self) -> dict:
        return self.raw["temporal_alignment"]

    # --- spatial alignment ---
    def spatial_alignment_cfg(self) -> dict:
        return self.raw["spatial_alignment"]

    # --- missing data ---
    def missing_data_cfg(self) -> dict:
        return self.raw["missing_data"]

    # --- normalization ---
    def normalization_cfg(self) -> dict:
        return self.raw["normalization"]

    # --- features ---
    def features_cfg(self) -> dict:
        return self.raw["features"]

    # --- sequence ---
    def sequence_cfg(self) -> dict:
        return self.raw["sequence"]

    # --- target ---
    def target_cfg(self) -> dict:
        return self.raw["target"]

    # --- split ---
    def split_cfg(self) -> dict:
        return self.raw["split"]

    # --- reproducibility ---
    def reproducibility_cfg(self) -> dict:
        return self.raw["reproducibility"]


def load_config(path: str | Path | None = None) -> PreprocessingConfig:
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(
            f"Preprocessing config not found at {config_path}. "
            "Pass an explicit path to load_config() or restore "
            "config/preprocessing_config.yaml."
        )
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    return PreprocessingConfig(raw=raw)
