"""
Stable output schema for M3 models.

Every model in src/models/ (persistence, classical_ml, convlstm, fusion)
must return a ModelOutput, regardless of internal architecture. This is the
contract M4 (evaluation) and M5 (API) build against.
"""

from dataclasses import dataclass
from typing import Optional, List
import torch


@dataclass
class ModelOutput:
    """
    prediction: torch.Tensor, shape [B, T_out, C_out, H, W]
        Matches DataContract.target_shape(). For target_type="binary" this
        is a probability map (post-sigmoid), not raw logits — kept explicit
        so M4 never has to guess whether to apply an activation.

    model_name: identifies which model produced this (e.g. "persistence",
        "classical_ml", "convlstm", "fusion").

    model_version: semantic version string, matches TrainConfig.model_version
        at training time (or a fixed baseline version for non-trained models).

    timestamps: optional list of ISO-8601 strings for each forecast step,
        length == forecast_horizon. PLACEHOLDER — M2 must confirm whether
        timestamp metadata travels with the input batch; until then this is
        left None and populated by inference/predict.py if available.

    metadata: free-form dict for anything else M4/M5 need (e.g. spatial
        bounding box, grid CRS) — placeholder until M1/M2 define it.
    """

    prediction: torch.Tensor
    model_name: str
    model_version: str
    timestamps: Optional[List[str]] = None
    metadata: Optional[dict] = None

    def as_dict(self) -> dict:
        """Serialization-friendly form (prediction kept as tensor; caller
        converts to list/numpy at the API boundary if needed)."""
        return {
            "prediction": self.prediction,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "timestamps": self.timestamps,
            "metadata": self.metadata,
        }
