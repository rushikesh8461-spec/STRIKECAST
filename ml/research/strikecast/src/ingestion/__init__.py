"""
StrikeCast M1 — Data Engineering & Multimodal Ingestion

This package is owned by Member 1 (Data Engineering & Multimodal Ingestion).
It is responsible for acquiring, loading, validating, standardizing metadata
for, and exposing raw/interim atmospheric data (satellite, lightning, NWP,
radar) to Member 2 (Spatio-Temporal Processing & Feature Engineering).

This package does NOT perform temporal/spatial alignment, imputation,
normalization, feature engineering, sequence construction, or train/val/test
splitting. Those are M2 responsibilities. See docs/m1_m2_contract.md.
"""

from .contract import (
    DataRecord,
    QualityReport,
    SourceType,
    QualityStatus,
)
from .base import BaseDataSource

__all__ = [
    "DataRecord",
    "QualityReport",
    "SourceType",
    "QualityStatus",
    "BaseDataSource",
]

__version__ = "0.1.0"
