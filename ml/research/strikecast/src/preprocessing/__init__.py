"""
StrikeCast M2 — Spatio-Temporal Processing & Feature Engineering.

Owned by Member 2. Converts M1's validated multimodal atmospheric
observations (src/ingestion) into clean, aligned, leakage-safe,
model-ready datasets/features for M3. See docs/m2_m3_contract.md for the
full M2 -> M3 interface specification.

This package does NOT perform raw data ingestion/acquisition (M1), model
architecture/training (M3), evaluation metrics/risk scoring (M4), the API
(M5), or the frontend (M6).

Public entry point:

    from src.preprocessing.config import load_config
    from src.preprocessing.dataset import build_dataset

    bundle = build_dataset(load_config())
"""

from .config import PreprocessingConfig, load_config
from .dataset import DatasetBundle, WindowDataset, build_dataset

__all__ = [
    "PreprocessingConfig",
    "load_config",
    "DatasetBundle",
    "WindowDataset",
    "build_dataset",
]

__version__ = "0.1.0"
