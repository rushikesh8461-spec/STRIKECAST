"""
Central configuration for the StrikeCast M3 module.

Every hyperparameter and tensor-shape assumption lives here. Nothing else in
src/ should hardcode a shape or hyperparameter value — import it from here.

Values marked "PLACEHOLDER" are not yet confirmed by M1/M2. They are set to
reasonable small defaults so the ConvLSTM pipeline can be built and shape-
tested with synthetic data today. When M2's real contract is finalized,
only this file (and the corresponding YAML) should need to change.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional
import torch


# ---------------------------------------------------------------------------
# Data contract (PLACEHOLDER — pending M1/M2 confirmation)
# ---------------------------------------------------------------------------

@dataclass
class DataContract:
    """
    Defines the exact tensor shapes M3 expects to receive from M2, and the
    shape M3 must produce for M4.

    Tensor ordering: [B, T, C, H, W]  (batch, time, channels, height, width)
    This is fixed by M3 (see rationale in chat). If M2 emits a different
    ordering, the adapter in dataset.py performs the permute — models never
    see anything but [B, T, C, H, W].
    """

    # --- Input (history window fed to the model) ---
    sequence_length: int = 6          # PLACEHOLDER: T, number of past timesteps
    input_channels: int = 1           # PLACEHOLDER: C, e.g. 1 modality (radar reflectivity) to start
    height: int = 32                  # PLACEHOLDER: H, spatial grid rows
    width: int = 32                   # PLACEHOLDER: W, spatial grid cols

    # --- Target ---
    forecast_horizon: int = 1         # PLACEHOLDER: number of future timesteps to predict
    target_type: Literal["continuous", "binary", "multiclass"] = "binary"
    # PLACEHOLDER — "binary" assumed (lightning strike / no strike per cell).
    # This choice drives losses.py (Phase 10) and schema.py. Confirm with M1/M2.
    num_classes: Optional[int] = None  # only used if target_type == "multiclass"

    # Required to make the lightning persistence baseline use the named,
    # train-normalized lightning-count input instead of an arbitrary channel.
    input_channel_names: Optional[List[str]] = None
    lightning_channel_index: Optional[int] = None
    lightning_zero_threshold: Optional[float] = None

    # --- Modalities (for multimodal fusion, Phase 8) ---
    # PLACEHOLDER — names/channel-counts unconfirmed. Each entry describes one
    # input stream that fusion.py will encode separately before fusing.
    modalities: List[str] = field(default_factory=lambda: ["radar"])
    modality_channels: dict = field(default_factory=lambda: {"radar": 1})

    # --- Dtype / device ---
    dtype: torch.dtype = torch.float32

    def input_shape(self, batch_size: int) -> tuple:
        """Expected input tensor shape: [B, T, C, H, W]"""
        return (batch_size, self.sequence_length, self.input_channels, self.height, self.width)

    def target_shape(self, batch_size: int) -> tuple:
        """
        Expected target tensor shape: [B, T_out, C_out, H, W]
        C_out = 1 for binary/continuous; num_classes for multiclass.
        """
        c_out = self.num_classes if self.target_type == "multiclass" else 1
        return (batch_size, self.forecast_horizon, c_out, self.height, self.width)

    @classmethod
    def from_m2_bundle(cls, bundle, split: str = "train", multimodal: bool = False) -> "DataContract":
        """
        Build a DataContract straight from an M2 `DatasetBundle` — the
        PLACEHOLDER values above stop being placeholders once real M2 data
        is in play. This is the single place that reads
        docs/m2_m3_contract.md's shapes so nothing else in src/ has to
        special-case "where did these numbers come from".

        `split` picks which WindowDataset to read a sample from (only used
        to confirm shapes match `bundle.metadata`; any non-empty split
        gives the same numbers). `multimodal=True` builds `modalities` /
        `modality_channels` from the channel schema's `source` field
        (grouping e.g. "radar" and "radar (derived)" together) instead of
        a single flat `input_channels`, for use with FusionConvLSTM.
        """
        from ml.training.strikecast_training.m2_bridge import channel_groups_by_source

        target_grid = bundle.metadata["target_grid"]
        target_mode = None
        for ds in bundle.splits.values():
            target_mode = ds.target_mode
            feature_schema = ds.get_feature_schema()
            break
        else:
            raise ValueError("bundle.splits is empty — cannot infer a DataContract from it.")

        target_type = "binary" if target_mode == "occurrence" else "continuous"

        kwargs = dict(
            sequence_length=bundle.metadata["sequence_length"],
            height=target_grid["n_lat"],
            width=target_grid["n_lon"],
            forecast_horizon=bundle.metadata["forecast_horizon"],
            target_type=target_type,
            input_channel_names=list(bundle.channel_names),
        )

        if target_type == "binary" and "lightning_strike_count" in bundle.channel_names:
            index = bundle.channel_names.index("lightning_strike_count")
            stats = bundle.normalization_stats["lightning_strike_count"]
            kwargs["lightning_channel_index"] = index
            kwargs["lightning_zero_threshold"] = (0.0 - float(stats["mean"])) / float(stats["std"])

        if multimodal:
            groups = channel_groups_by_source(feature_schema)
            kwargs["modalities"] = list(groups.keys())
            kwargs["modality_channels"] = {m: len(idxs) for m, idxs in groups.items()}
            kwargs["input_channels"] = len(bundle.channel_names)  # unused by fusion but kept consistent
        else:
            kwargs["input_channels"] = len(bundle.channel_names)

        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Training hyperparameters
# ---------------------------------------------------------------------------

@dataclass
class TrainConfig:
    # Reproducibility
    seed: int = 42

    # Data
    batch_size: int = 4
    num_workers: int = 0              # 0 for deterministic synthetic dev runs

    # Optimization
    learning_rate: float = 1e-3
    weight_decay: float = 0.0
    epochs: int = 5
    optimizer: Literal["adam", "sgd"] = "adam"
    loss: str = "bce"                 # must match target_type; resolved in losses.py

    # ConvLSTM architecture
    conv_hidden_dims: List[int] = field(default_factory=lambda: [16, 16])  # per-layer hidden channels
    conv_kernel_size: int = 3

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    checkpoint_every_n_epochs: int = 1

    # Device
    device: str = "cpu"               # overridden at runtime if CUDA available

    # Model identity (for schema.py / checkpoint metadata)
    model_name: str = "convlstm"
    model_version: str = "0.1.0"

    # --- Data source (M2 integration) ---
    # "synthetic": SyntheticDataset, matching DataContract exactly (dev/shape-testing).
    # "m2": real data via src.preprocessing.dataset.build_dataset(); the
    #       DataContract shape fields are then *derived* from the bundle
    #       (DataContract.from_m2_bundle) rather than read from YAML, since
    #       the real grid/channel/target shapes are only known once M2 has
    #       actually run — see src/training/m2_bridge.py.
    data_source: Literal["synthetic", "m2"] = "synthetic"
    m2_preprocessing_config: Optional[str] = None  # None = M2's own default config path
    m2_demo: bool = True                            # True = bundled data/sample_demo


@dataclass
class Config:
    data: DataContract = field(default_factory=DataContract)
    train: TrainConfig = field(default_factory=TrainConfig)
