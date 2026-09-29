"""
Persistence baseline: the simplest possible forecast — "whatever happened
last, will happen again." No learnable parameters.

For target_type == "binary": repeats the last observed frame's first
channel, squashed to [0,1] via clamp (input is raw signal, not a
probability, so we clamp rather than assume it's already bounded).
For "continuous": repeats the last observed frame as-is.
For "multiclass": not well-defined for a naive persistence baseline over
raw signal — raises NotImplementedError with a clear message rather than
silently producing nonsense.
"""

import torch

from src.models.base import BaseForecastModel
from src.models.schema import ModelOutput
from ml.training.strikecast_training.config import DataContract


class PersistenceBaseline(BaseForecastModel):
    model_name = "persistence"
    model_version = "1.0.0"

    def __init__(self, contract: DataContract):
        super().__init__(contract)
        if contract.target_type == "multiclass":
            raise NotImplementedError(
                "PersistenceBaseline has no defined behavior for "
                "target_type='multiclass' — requires a class-index mapping "
                "that hasn't been specified. Extend this explicitly once "
                "the multiclass target definition is confirmed."
            )
        if contract.target_type == "binary" and (
            contract.lightning_channel_index is None or contract.lightning_zero_threshold is None
        ):
            raise ValueError(
                "Binary lightning persistence requires the named lightning_strike_count "
                "channel and its train-normalized zero threshold from the M2 bundle."
            )

    def trainable(self) -> bool:
        return False

    def predict(self, x: torch.Tensor) -> ModelOutput:
        if isinstance(x, dict):
            # Multimodal input: persistence uses the first listed modality.
            x = x[self.contract.modalities[0]]

        # x: [B, T, C, H, W]. Binary occurrence persistence uses the
        # train-normalized lightning count channel, not an arbitrary first channel.
        channel = self.contract.lightning_channel_index if self.contract.target_type == "binary" else 0
        last_frame = x[:, -1, channel:channel + 1, :, :]

        if self.contract.target_type == "binary":
            last_frame = (last_frame > self.contract.lightning_zero_threshold).to(x.dtype)

        # Repeat across forecast_horizon
        horizon = self.contract.forecast_horizon
        prediction = last_frame.unsqueeze(1).repeat(1, horizon, 1, 1, 1)  # [B,T_out,1,H,W]

        return ModelOutput(
            prediction=prediction,
            model_name=self.model_name,
            model_version=self.model_version,
        )
