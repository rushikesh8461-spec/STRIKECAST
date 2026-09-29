"""Train-period, per-grid-cell event-frequency climatology baseline."""
from __future__ import annotations

import torch

from ml.training.strikecast_training.config import DataContract
from src.models.base import BaseForecastModel
from src.models.schema import ModelOutput


class ClimatologyBaseline(BaseForecastModel):
    """Predict each cell's binary event frequency from TRAIN labels only."""

    model_name = "climatology"
    model_version = "1.0.0"

    def __init__(self, contract: DataContract):
        super().__init__(contract)
        if contract.target_type != "binary":
            raise ValueError("ClimatologyBaseline supports binary occurrence targets only")
        self._probability_map: torch.Tensor | None = None

    def trainable(self) -> bool:
        return False

    def fit(self, y_train: torch.Tensor, observation_mask: torch.Tensor | None = None) -> "ClimatologyBaseline":
        """Fit per-cell probabilities on TRAIN labels; y=[N,H,1,lat,lon]."""
        y = torch.as_tensor(y_train, dtype=torch.float32)
        expected = (self.contract.forecast_horizon, 1, self.contract.height, self.contract.width)
        if y.ndim != 5 or tuple(y.shape[1:]) != expected or y.shape[0] < 1:
            raise ValueError(f"y_train must have shape [N,{expected[0]},1,{expected[2]},{expected[3]}]")
        mask = torch.ones_like(y, dtype=torch.bool) if observation_mask is None else torch.as_tensor(observation_mask, dtype=torch.bool)
        if mask.shape != y.shape:
            raise ValueError("observation_mask must match y_train")
        observed = y[mask]
        if observed.numel() == 0 or not torch.isfinite(observed).all() or not torch.isin(observed, torch.tensor([0.0, 1.0])).all():
            raise ValueError("climatology requires observed finite binary training labels")
        counts = mask.sum(dim=0)
        sums = torch.where(mask, y, 0.0).sum(dim=0)
        global_rate = observed.mean()
        self._probability_map = torch.where(counts > 0, sums / counts.clamp_min(1), global_rate).detach()
        return self

    def predict(self, x) -> ModelOutput:
        if self._probability_map is None:
            raise RuntimeError("ClimatologyBaseline must be fit on TRAIN labels before prediction")
        reference = next(iter(x.values())) if isinstance(x, dict) else x
        probability = self._probability_map.to(reference.device, dtype=reference.dtype)
        prediction = probability.unsqueeze(0).expand(reference.shape[0], *probability.shape)
        return ModelOutput(prediction=prediction, model_name=self.model_name, model_version=self.model_version)
