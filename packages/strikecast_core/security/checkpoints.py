"""Safe, checksum-pinned PyTorch checkpoint loading."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import torch


def load_verified_checkpoint(path: Path, expected_sha256: str, expected_metadata: dict[str, Any]) -> dict[str, Any]:
    """Load a weights-only checkpoint after exact digest and metadata checks."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("Model artifact is missing")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("Model artifact checksum does not match the registered artifact")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    required = {"state_dict", "input_features", "sequence_length", "grid_size", "model_name", "model_version"}
    if not isinstance(checkpoint, dict) or set(checkpoint) != required:
        raise ValueError("Model checkpoint metadata is incompatible")
    if not isinstance(checkpoint["state_dict"], dict):
        raise ValueError("Model checkpoint state is incompatible")
    if any(checkpoint.get(key) != value for key, value in expected_metadata.items()):
        raise ValueError("Model checkpoint metadata does not match the registered model")
    return checkpoint
