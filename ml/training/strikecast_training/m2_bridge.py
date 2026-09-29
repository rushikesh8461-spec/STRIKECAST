"""
The M2 <-> M3 integration point.

Before this module existed, M2 (src/preprocessing, src/ingestion,
src/features) and M3 (src/models, src/training, src/inference) were two
independently-built halves that had never been run against each other:
M3's training and inference entrypoints only ever constructed
`SyntheticDataset` (see dataset.py's module docstring — "a new class (e.g.
M2Dataset) ... is swapped in via config" was still a TODO). This module is
that class, plus the small amount of glue `train.py` / `predict.py` need to
use it.

What this file does, concretely:

  * `load_m2_bundle(...)` — thin wrapper around
    `src.preprocessing.dataset.build_dataset`, imported lazily so M3 code
    that never touches real data has no hard M2 import at load time.
  * `channel_groups_by_source(...)` — reads the `source` field M2 already
    attaches to every channel (`WindowDataset.get_feature_schema()`) and
    groups channel indices by base source (satellite/nwp/radar/lightning),
    stripping the "(derived)" suffix so a base feature and its derived
    counterpart land in the same group. This is what lets
    FusionConvLSTM's per-modality encoders receive M2's single stacked
    `[T, H, W, C]` tensor split back into per-source tensors, without
    hardcoding channel names/counts anywhere.
  * `M2Dataset` — wraps one M2 `WindowDataset` split as a
    `StrikeCastDataset` (single-tensor contract: `ConvLSTM`,
    `classical_ml`, `persistence`).
  * `M2MultimodalDataset` — same, but for `FusionConvLSTM`'s
    `dict[str, Tensor]` contract.

Both dataset classes perform the **exact** transform documented in
docs/m2_m3_contract.md and verified against the bundled demo data:

    M2 X: [L, lat, lon, C]  (float32, z-score normalized, no NaN)
        -> torch [L, C, lat, lon]           (permute; matches DataContract's
                                              fixed [T, C, H, W] ordering)
    M2 y: [H, lat, lon]     (float32; {0,1} if target.mode == "occurrence",
                             raw counts if "strike_count")
        -> torch [H, 1, lat, lon]            (unsqueeze the channel dim
                                              ConvLSTM/Fusion always predict)

`mask` ([L, lat, lon, C], bool) is deliberately **not** folded into the
(x, y) tuple returned by `__getitem__` — that would break the
`StrikeCastDataset` contract every model/training-loop call site relies on.
docs/m2_m3_contract.md is explicit that the MVP baseline doesn't need it
("any window with too high a missing fraction has already been dropped").
It stays available via `.get_mask(idx)` on both classes for anyone
building masked-loss training later.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import torch

from ml.training.strikecast_training.config import DataContract
from ml.training.strikecast_training.dataset import StrikeCastDataset


def load_m2_bundle(preprocessing_config_path: Optional[str] = None, demo: bool = True):
    """Load an M2 `DatasetBundle`. Lazy-imports src.preprocessing so nothing
    in src/training or src/models is forced to depend on M2 at import time
    (SyntheticDataset-only training/inference keeps working with zero M2
    installed/importable)."""
    from src.preprocessing.config import load_config
    from src.preprocessing.dataset import build_dataset

    config = load_config(preprocessing_config_path)
    return build_dataset(config, demo=demo)


def channel_groups_by_source(feature_schema: List[dict]) -> Dict[str, List[int]]:
    """
    Group channel indices by base source, in first-appearance order.

    feature_schema is `WindowDataset.get_feature_schema()` — a list of
    per-channel dicts (one per entry in `bundle.channel_names`, same
    order) each with a `source` field like "satellite", "nwp",
    "nwp (derived)", "radar (derived)", etc. (see src/features/schema.py).
    A derived feature's source is always "<base source> (derived)", so
    splitting on the first space and discarding the rest groups e.g.
    reflectivity (radar) with reflectivity_dt/reflectivity_spatial_gradient_mag
    (both "radar (derived)") into one "radar" modality — never a hardcoded
    channel-name list.
    """
    groups: Dict[str, List[int]] = {}
    for idx, spec in enumerate(feature_schema):
        base_source = spec["source"].split(" ")[0]
        groups.setdefault(base_source, []).append(idx)
    return groups


def _to_target_tensor(y: np.ndarray, dtype: torch.dtype) -> torch.Tensor:
    """[H, lat, lon] -> [H, 1, lat, lon] torch tensor."""
    t = torch.from_numpy(np.ascontiguousarray(y)).to(dtype)
    return t.unsqueeze(1)


class M2Dataset(StrikeCastDataset):
    """
    Single-tensor adapter for an M2 `WindowDataset` split, for
    single-input models (ConvLSTM, classical_ml, persistence).

    __getitem__(idx) -> (x, y) matching StrikeCastDataset's contract:
        x: torch.Tensor [T, C, H, W]      (T=contract.sequence_length,
                                            C=contract.input_channels)
        y: torch.Tensor [T_out, 1, H, W]
    """

    def __init__(self, window_dataset, contract: DataContract):
        super().__init__(contract)
        self.window_dataset = window_dataset
        expected_channels = len(window_dataset.channel_names)
        if contract.input_channels != expected_channels:
            raise ValueError(
                f"DataContract.input_channels={contract.input_channels} does not "
                f"match the M2 dataset's {expected_channels} channels "
                f"({window_dataset.channel_names}). Build the contract with "
                f"DataContract.from_m2_bundle(bundle) rather than hand-writing it."
            )

    def __len__(self) -> int:
        return len(self.window_dataset)

    def __getitem__(self, idx: int):
        sample = self.window_dataset[idx]
        x = torch.from_numpy(np.ascontiguousarray(sample["X"])).to(self.contract.dtype)
        x = x.permute(0, 3, 1, 2).contiguous()  # [L, lat, lon, C] -> [L, C, lat, lon]
        y = _to_target_tensor(sample["y"], self.contract.dtype)
        return x, y

    def get_mask(self, idx: int) -> torch.Tensor:
        """[L, C, H, W] bool — not part of the (x, y) contract; see module
        docstring. True = real/interpolated observation, False = filled
        placeholder."""
        mask = self.window_dataset[idx]["mask"]
        return torch.from_numpy(np.ascontiguousarray(mask)).permute(0, 3, 1, 2).contiguous()


class M2MultimodalDataset(StrikeCastDataset):
    """
    dict[str, Tensor] adapter for an M2 `WindowDataset` split, for
    FusionConvLSTM. Splits M2's single stacked [L, lat, lon, C] tensor back
    into one [T, C_m, H, W] tensor per modality using `channel_groups_by_source`.
    """

    def __init__(self, window_dataset, contract: DataContract):
        super().__init__(contract)
        self.window_dataset = window_dataset
        self.groups = channel_groups_by_source(window_dataset.get_feature_schema())

        missing = set(contract.modalities) - set(self.groups.keys())
        if missing:
            raise ValueError(
                f"DataContract.modalities={contract.modalities} references "
                f"modalities not present in the M2 dataset's channels "
                f"({list(self.groups.keys())}): {missing}. Build the contract "
                f"with DataContract.from_m2_bundle(bundle, multimodal=True)."
            )
        for m in contract.modalities:
            expected = len(self.groups[m])
            if contract.modality_channels.get(m) != expected:
                raise ValueError(
                    f"DataContract.modality_channels['{m}']="
                    f"{contract.modality_channels.get(m)} does not match the "
                    f"M2 dataset's {expected} channels for that source."
                )

    def __len__(self) -> int:
        return len(self.window_dataset)

    def __getitem__(self, idx: int):
        sample = self.window_dataset[idx]
        X = sample["X"]  # [L, lat, lon, C]
        x = {}
        for m in self.contract.modalities:
            idxs = self.groups[m]
            x_m = torch.from_numpy(np.ascontiguousarray(X[..., idxs])).to(self.contract.dtype)
            x[m] = x_m.permute(0, 3, 1, 2).contiguous()  # [L, lat, lon, C_m] -> [L, C_m, lat, lon]
        y = _to_target_tensor(sample["y"], self.contract.dtype)
        return x, y


def build_m2_dataset(window_dataset, contract: DataContract, multimodal: bool) -> StrikeCastDataset:
    """Convenience factory so train.py/predict.py don't need to import both
    dataset classes and pick one inline."""
    if multimodal:
        return M2MultimodalDataset(window_dataset, contract)
    return M2Dataset(window_dataset, contract)
