"""
Abstract interface every M3 model (persistence, classical ML, ConvLSTM,
fusion) implements. Guarantees training.train.py and inference.predict.py
can treat all four models identically.
"""

from abc import ABC, abstractmethod
from typing import Optional
import torch
import torch.nn as nn

from src.models.schema import ModelOutput
from ml.training.strikecast_training.config import DataContract


class BaseForecastModel(ABC):
    """
    Common contract:
      - trainable() tells the training loop whether this model needs
        gradient-based training (deep models) or its own fit() call
        (classical ML) or nothing at all (persistence).
      - predict(x) always returns a ModelOutput with `prediction` shaped
        exactly as DataContract.target_shape() (minus batch dim mismatch
        checks — caller batch size flows through).
    """

    model_name: str = "base"
    model_version: str = "0.0.0"

    def __init__(self, contract: DataContract):
        self.contract = contract

    @abstractmethod
    def trainable(self) -> bool:
        """True if this model should go through the gradient-based training
        loop in training/train.py. False for persistence (no params) and
        classical_ml (fits via sklearn, not via the torch training loop)."""
        ...

    @abstractmethod
    def predict(self, x) -> ModelOutput:
        """x: torch.Tensor [B,T,C,H,W] or dict[str, Tensor] for multimodal.
        Returns ModelOutput with prediction shaped [B,T_out,C_out,H,W]."""
        ...


class BaseForecastNNModel(BaseForecastModel, nn.Module):
    """Base for the deep-learning models (ConvLSTM, Fusion) — combines the
    M3 contract with nn.Module so these can be trained via train.py."""

    def __init__(self, contract: DataContract):
        nn.Module.__init__(self)
        BaseForecastModel.__init__(self, contract)

    def trainable(self) -> bool:
        return True

    @abstractmethod
    def forward(self, x):
        """Raw forward pass, returns prediction tensor [B,T_out,C_out,H,W].
        predict() wraps this with the ModelOutput schema."""
        ...

    def predict(self, x) -> ModelOutput:
        self.eval()
        with torch.no_grad():
            out = self.forward(x)
        return ModelOutput(
            prediction=out,
            model_name=self.model_name,
            model_version=self.model_version,
        )
