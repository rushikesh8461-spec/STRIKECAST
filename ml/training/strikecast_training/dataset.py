"""
M2 -> M3 dataset contract.

`StrikeCastDataset` is the abstract interface every dataset M3 trains on
must satisfy. `SyntheticDataset` is a concrete implementation that generates
random tensors matching `DataContract` exactly — it exists so the ConvLSTM,
training loop, checkpointing, and inference path can all be built and
verified *before* M2's real preprocessing pipeline is available.

M2 is now integrated: `src/training/m2_bridge.py` implements
`M2Dataset` / `M2MultimodalDataset`, the same `__getitem__` contract below,
backed by `src.preprocessing.dataset.build_dataset()`'s real windows.
`train.py` / `predict.py` select between this file's `SyntheticDataset` and
`m2_bridge`'s real-data classes via `TrainConfig.data_source`
("synthetic" | "m2") — no other file in src/ needed to change.

Contract (fixed by M3, see chat rationale):
    __getitem__(idx) -> (x, y)
        x: torch.Tensor, shape [T, C, H, W]      (single sample; DataLoader adds B)
        y: torch.Tensor, shape [T_out, C_out, H, W]
    Batched by DataLoader -> [B, T, C, H, W] / [B, T_out, C_out, H, W]

If M2 exposes multiple modalities (Phase 8), __getitem__ instead returns
    x: dict[str, torch.Tensor]   one [T, C_m, H, W] tensor per modality
    y: torch.Tensor              same target shape as above
This dict form is only used when `data.modalities` has more than one entry.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Union, Dict
import torch
from torch.utils.data import Dataset

from ml.training.strikecast_training.config import DataContract


SampleInput = Union[torch.Tensor, Dict[str, torch.Tensor]]


class StrikeCastDataset(Dataset, ABC):
    """Abstract base every M3-compatible dataset must implement."""

    def __init__(self, contract: DataContract):
        self.contract = contract

    @abstractmethod
    def __len__(self) -> int:
        ...

    @abstractmethod
    def __getitem__(self, idx: int) -> Tuple[SampleInput, torch.Tensor]:
        ...


class SyntheticDataset(StrikeCastDataset):
    """
    Generates random data matching `DataContract` exactly. Used for:
      - validating ConvLSTM tensor shapes (Step 5)
      - training-loop smoke tests (Step 6)
      - checkpoint save/load round-trip tests (Step 7)
      - inference path tests (Step 8)

    Not intended to produce meaningful predictions — purely a shape/plumbing
    fixture until M2's real dataset is available.
    """

    def __init__(self, contract: DataContract, num_samples: int = 32, seed: int = 0):
        super().__init__(contract)
        self.num_samples = num_samples
        # Fixed generator so the synthetic dataset itself is reproducible,
        # independent of whatever global seed training uses.
        self._generator = torch.Generator().manual_seed(seed)

        c = self.contract
        multimodal = len(c.modalities) > 1

        self._x = []
        self._y = []
        for _ in range(num_samples):
            if multimodal:
                sample_x = {
                    m: torch.randn(
                        c.sequence_length, c.modality_channels[m], c.height, c.width,
                        generator=self._generator, dtype=c.dtype,
                    )
                    for m in c.modalities
                }
            else:
                sample_x = torch.randn(
                    c.sequence_length, c.input_channels, c.height, c.width,
                    generator=self._generator, dtype=c.dtype,
                )

            c_out = c.num_classes if c.target_type == "multiclass" else 1
            if c.target_type == "binary":
                sample_y = torch.randint(
                    0, 2, (c.forecast_horizon, c_out, c.height, c.width),
                    generator=self._generator,
                ).to(c.dtype)
            elif c.target_type == "multiclass":
                sample_y = torch.randint(
                    0, c.num_classes, (c.forecast_horizon, c.height, c.width),
                    generator=self._generator,
                ).long()
            else:  # continuous
                sample_y = torch.randn(
                    c.forecast_horizon, c_out, c.height, c.width,
                    generator=self._generator, dtype=c.dtype,
                )

            self._x.append(sample_x)
            self._y.append(sample_y)

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[SampleInput, torch.Tensor]:
        return self._x[idx], self._y[idx]
