"""Fail-closed local candidate validation and explicit production rollback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
import tempfile
from typing import Any

REQUIRED = {"model.pt", "model_metadata.json", "dataset_manifest.json", "feature_schema.json",
            "target_schema.json", "normalization.json", "training_config.yaml", "metrics.json",
            "calibration.json", "checksums.sha256", "model_card.md"}
SUPPORTED_ARCHITECTURES = {"ConvLSTMClassifier", "StrikeCastConvLSTM"}
from ..features.served_schema import SERVED_FEATURE_SCHEMA_VERSION, SERVED_NORMALIZATION_VERSION
SERVED_INPUT_SHAPE = [6, 8, 3, 3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_model_artifact(directory: str | Path, *, expected_schema_version: str | None = None,
                            expected_dataset_version: str | None = None) -> dict[str, Any]:
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError("model artifact directory is missing")
    missing = sorted(name for name in REQUIRED if not (root / name).is_file())
    if missing:
        raise ValueError(f"model artifact missing required files: {', '.join(missing)}")
    metadata = json.loads((root / "model_metadata.json").read_text(encoding="utf-8"))
    required_meta = ("model_version", "architecture", "schema_version", "dataset_version",
                     "feature_schema_version", "served_feature_schema_version", "normalization_version")
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in required_meta):
        raise ValueError("model_metadata.json lacks required version/architecture fields")
    if metadata["architecture"] not in SUPPORTED_ARCHITECTURES:
        raise ValueError("unsupported model architecture")
    if expected_schema_version and metadata["schema_version"] != expected_schema_version:
        raise ValueError("model schema version mismatch")
    if expected_dataset_version and metadata["dataset_version"] != expected_dataset_version:
        raise ValueError("model dataset version mismatch")
    checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    declared = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line.strip())
        if not match:
            raise ValueError("checksums.sha256 has an invalid line")
        declared[match.group(2)] = match.group(1)
    for name in REQUIRED - {"checksums.sha256"}:
        if declared.get(name) != _sha256(root / name):
            raise ValueError(f"checksum mismatch or missing digest for {name}")
    parsed={}
    for name in ("dataset_manifest.json", "feature_schema.json", "target_schema.json", "normalization.json", "metrics.json", "calibration.json"):
        try:
            parsed[name]=json.loads((root / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{name} is invalid JSON") from exc
    shape=metadata["model_input_shape"]
    if not isinstance(shape,list) or not shape or any(type(v) is not int or v<=0 for v in shape):
        raise ValueError("model_input_shape must contain positive integer dimensions")
    if parsed["feature_schema.json"].get("schema_version")!=metadata["feature_schema_version"]:
        raise ValueError("feature schema metadata mismatch")
    if parsed["normalization.json"].get("normalization_version")!=metadata["normalization_version"]:
        raise ValueError("normalization metadata mismatch")
    if parsed["dataset_manifest.json"].get("dataset_version")!=metadata["dataset_version"]:
        raise ValueError("dataset manifest metadata mismatch")
    try:
        import torch
        torch.load(root / "model.pt", map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ValueError("model.pt is not a supported safe-load checkpoint") from exc
    compatible=(metadata["architecture"]=="ConvLSTMClassifier"
                and metadata["model_input_shape"]==SERVED_INPUT_SHAPE
                and metadata["served_feature_schema_version"]==SERVED_FEATURE_SCHEMA_VERSION
                and metadata["feature_schema_version"]=="point-feature-v1"
                and metadata["normalization_version"]==SERVED_NORMALIZATION_VERSION)
    return {"status": "VALID_CANDIDATE", "api_compatibility":"SUPPORTED" if compatible else "UNSUPPORTED",
            "model_version": metadata["model_version"],
            "schema_version": metadata["schema_version"], "dataset_version": metadata["dataset_version"],
            "architecture": metadata["architecture"]}


def validate_serving_compatibility(directory: str | Path) -> dict[str, Any]:
    """Validate a checksummed artifact and refuse research-only model contracts."""
    result=validate_model_artifact(directory)
    if result["api_compatibility"]!="SUPPORTED":
        raise ValueError("INFERENCE_COMPATIBILITY=UNSUPPORTED for registered model artifact")
    return result


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".registry-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _resolve_version(registry: Path, pointer: dict[str, Any]) -> Path:
    relative = pointer.get("artifact")
    if (not isinstance(relative, str) or Path(relative).is_absolute()
            or PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts or ".." in PureWindowsPath(relative).parts
            or "\\" in relative):
        raise ValueError("registry pointer contains an unsafe artifact path")
    artifact = (registry / relative).resolve()
    if registry.resolve() not in artifact.parents:
        raise ValueError("registry pointer escapes registry root")
    return artifact


def promote_candidate(registry_dir: str | Path, candidate_dir: str | Path) -> dict[str, Any]:
    """Explicit operator call; candidate validated before pointers are changed."""
    registry = Path(registry_dir).resolve()
    candidate = Path(candidate_dir).resolve()
    validate_serving_compatibility(candidate)
    versions_root = (registry / "versions").resolve()
    if versions_root not in candidate.parents:
        raise ValueError("candidate must be stored beneath registry/versions")
    current_file, previous_file = registry / "current.json", registry / "previous.json"
    new = {"artifact": candidate.relative_to(registry).as_posix(), "model_version": candidate.name}
    old = json.loads(current_file.read_text(encoding="utf-8")) if current_file.is_file() else None
    if old:
        validate_model_artifact(_resolve_version(registry, old))
        _atomic_json(previous_file, old)
    _atomic_json(current_file, new)
    return {"status": "PROMOTED_EXPLICITLY", "current": new, "previous": old}


def rollback_production(registry_dir: str | Path) -> dict[str, Any]:
    registry = Path(registry_dir).resolve()
    current_file, previous_file = registry / "current.json", registry / "previous.json"
    if not current_file.is_file() or not previous_file.is_file():
        raise ValueError("both current and previous production pointers are required for rollback")
    current = json.loads(current_file.read_text(encoding="utf-8"))
    previous = json.loads(previous_file.read_text(encoding="utf-8"))
    validate_model_artifact(_resolve_version(registry, previous))
    validate_model_artifact(_resolve_version(registry, current))
    _atomic_json(current_file, previous)
    _atomic_json(previous_file, current)
    return {"status": "ROLLED_BACK", "current": previous, "previous": current}
