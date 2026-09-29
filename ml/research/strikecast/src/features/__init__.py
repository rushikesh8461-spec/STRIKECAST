"""
StrikeCast M2 — Feature engineering.

Owned by Member 2 (Spatio-Temporal Processing & Feature Engineering).
Defines the fixed, documented channel schema (schema.py) and the derived-
feature computations (engineering.py) used by src/preprocessing to build
the model-ready feature tensor handed to M3.
"""

from .schema import BASE_FEATURES, DERIVED_FEATURES, get_feature_schema, resolve_channel_order

__all__ = [
    "BASE_FEATURES",
    "DERIVED_FEATURES",
    "get_feature_schema",
    "resolve_channel_order",
]
