"""
Model loading abstraction.

The API must never contain ConvLSTM implementation details. FastAPI routes
only ever talk to `InferenceService` (see inference_service.py), which in
turn only ever talks to whatever `BaseModel` this loader hands back.

Two implementations:
  - MockModel: deterministic, dependency-free, used when MODEL_MODE=mock.
  - RealModel: thin wrapper that will load an actual M3 checkpoint when
    MODEL_MODE=real. It is intentionally minimal - M3 owns the checkpoint
    format and the real inference math. This wrapper's only job is to load
    the file safely and expose the same `.predict(x)` interface as MockModel
    so nothing above this layer needs to change when the swap happens.

Swap point: replace MockModel with RealModel by setting MODEL_MODE=real and
MODEL_PATH=/path/to/checkpoint - no FastAPI route changes required.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from api.config import Settings

logger = logging.getLogger("strikecast.model_loader")


class ModelLoadError(Exception):
    """Raised when a model checkpoint cannot be loaded or is invalid."""


class InferenceModel(Protocol):
    """The only interface the rest of the API is allowed to depend on."""

    name: str
    version: str

    def predict(self, x: Dict[str, Any]) -> Dict[str, Any]:
        ...


@dataclass
class MockModel:
    """Deterministic mock model for development and CI.

    Deterministic means: the same input always produces the same output, so
    tests and M6 frontend development can rely on stable fixtures. Determinism
    is achieved by deriving pseudo-random-looking-but-stable values from a
    hash of the input rather than from `random`/`numpy.random` without a seed.
    """

    name: str = "mock-convlstm"
    version: str = "0.0.0-mock"

    def predict(self, x: Dict[str, Any]) -> Dict[str, Any]:
        lat = x.get("latitude", 0.0)
        lon = x.get("longitude", 0.0)
        horizon = x.get("horizon_minutes", 60)
        grid = x.get("grid")

        seed_str = f"{lat:.4f}:{lon:.4f}:{horizon}"
        digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        # Turn the first 8 hex chars into a stable float in [0, 1).
        pseudo = int(digest[:8], 16) / 0xFFFFFFFF

        probability = round(pseudo, 4)
        prediction = round(pseudo * 100, 2)  # e.g. a mock "rainfall intensity" score
        confidence = round(0.6 + 0.4 * (1 - pseudo), 4)  # inversely related, just for variety

        grid_shape: Optional[List[int]] = None
        if grid is not None:
            grid_shape = [len(grid), len(grid[0]) if grid else 0, len(grid[0][0]) if grid and grid[0] else 0]

        return {
            "prediction": prediction,
            "probability": probability,
            "confidence": confidence,
            "grid_shape": grid_shape,
        }


class RealModel:
    """Wrapper around an actual M3 checkpoint.

    This is a placeholder integration point. M3's real inference details
    (architecture, preprocessing, postprocessing) belong in the M3 module -
    this class should only need to change to point at whatever loader
    function M3 exposes.
    """

    def __init__(self, model_path: str, version: str, registry_dir: str = "./models/registry", expected_sha256: str = ""):
        self.name = "convlstm"
        self.version = version
        self._model_path = model_path
        self._checkpoint = self._load_checkpoint(model_path, registry_dir, expected_sha256)

    @staticmethod
    def _load_checkpoint(model_path: str, registry_dir: str, expected_sha256: str) -> Any:
        if not model_path:
            raise ModelLoadError("MODEL_PATH is not set but MODEL_MODE=real was requested.")
        registry = Path(registry_dir).resolve()
        path = Path(model_path)
        path = (registry / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(registry) or path.suffix.lower() != ".pt":
            raise ModelLoadError("Model path must resolve to a .pt file inside MODEL_REGISTRY_DIR.")
        if not path.exists():
            raise ModelLoadError("Allowlisted model checkpoint is not present.")
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256):
            raise ModelLoadError("MODEL_SHA256 must contain the registered checkpoint SHA-256.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.lower() != expected_sha256.lower():
            raise ModelLoadError("Model checkpoint checksum verification failed.")

        try:
            import torch  # Imported lazily: only required in real mode.
        except ImportError as exc:
            raise ModelLoadError(
                "PyTorch is required for MODEL_MODE=real but is not installed."
            ) from exc

        try:
            # weights_only=True avoids unsafe deserialization of arbitrary
            # pickled objects - only tensors/params are loaded.
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        except Exception as exc:  # noqa: BLE001 - surfaced as a clean ModelLoadError
            raise ModelLoadError("Failed to safely deserialize model checkpoint.") from exc

        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("state_dict"), dict):
            raise ModelLoadError("Checkpoint state dictionary is missing or incompatible.")
        metadata = checkpoint.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("model_version") is None or metadata.get("model_name") is None:
            raise ModelLoadError("Checkpoint model metadata is missing or incompatible.")

        return checkpoint

    def predict(self, x: Dict[str, Any]) -> Dict[str, Any]:
        # Intentionally not implemented: the real ConvLSTM forward pass and
        # any pre/post-processing belongs to M3. Wire it up here once M3's
        # inference function is available, e.g.:
        #
        #   from m3.inference import predict as m3_predict
        #   return m3_predict(self._checkpoint, x)
        raise NotImplementedError(
            "RealModel.predict() is a placeholder - integrate M3's inference "
            "function here once the trained checkpoint/interface is available."
        )


class ModelLoader:
    """Loads exactly one model instance at startup and keeps it in memory."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: Optional[InferenceModel] = None
        self._ready: bool = False
        self._load_error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def model(self) -> Optional[InferenceModel]:
        return self._model

    def load(self) -> None:
        """Load the model once. Never reload per-request."""
        try:
            if self._settings.is_mock_mode:
                logger.info("Loading MockModel (MODEL_MODE=mock).")
                self._model = MockModel(version=self._settings.model_version or "0.0.0-mock")
            else:
                logger.info("Loading registered real model in mode=%s", self._settings.model_mode)
                self._model = RealModel(
                    model_path=self._settings.model_path,
                    version=self._settings.model_version,
                    registry_dir=self._settings.model_registry_dir,
                    expected_sha256=self._settings.model_checksum,
                )
            self._ready = True
            self._load_error = None
            logger.info(
                "Model ready: name=%s version=%s mode=%s",
                self._model.name,
                self._model.version,
                self._settings.model_mode,
            )
        except ModelLoadError as exc:
            self._ready = False
            self._load_error = str(exc)
            logger.error("Model loading failed: %s", exc)
        except Exception as exc:  # noqa: BLE001 - never crash startup
            self._ready = False
            self._load_error = f"Unexpected error while loading model: {exc}"
            logger.exception("Unexpected error while loading model.")
