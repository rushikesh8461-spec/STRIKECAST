"""
Checkpoint save/load for the gradient-trained models (ConvLSTM, Fusion).
Persistence has no parameters; ClassicalMLBaseline uses its own
serialization (joblib) — see classical_ml checkpoint helpers below.

Checkpoint contents (deep models):
    model_state_dict
    optimizer_state_dict
    epoch
    config (dataclasses, as plain dicts — reconstructable without importing
            the exact dataclass version, and safe to torch.save)
    seed
    model_name / model_version
"""

import os
import dataclasses
import torch

from ml.training.strikecast_training.config import Config, DataContract, TrainConfig
from src.models.factory import build_model


def save_checkpoint(model, optimizer, epoch: int, config: Config, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
        "epoch": epoch,
        "data_config": dataclasses.asdict(config.data),
        "train_config": dataclasses.asdict(config.train),
        "seed": config.train.seed,
        "model_name": model.model_name,
        "model_version": model.model_version,
    }
    torch.save(checkpoint, path)
    return path


def load_checkpoint(path: str, device: str = "cpu"):
    """
    Returns (model, optimizer_state_dict, epoch, config).
    Rebuilds the model architecture from the saved config before loading
    weights — the checkpoint is self-describing, so inference never needs
    the training script's in-memory config.
    """
    # Training checkpoints contain tensors and primitive dict/list metadata only.
    # Never enable arbitrary pickle deserialization for a supplied artifact.
    checkpoint = torch.load(path, map_location=device, weights_only=True)

    data_cfg = DataContract(**checkpoint["data_config"])
    train_cfg = TrainConfig(**checkpoint["train_config"])
    config = Config(data=data_cfg, train=train_cfg)

    model = build_model(checkpoint["model_name"], data_cfg, train_cfg)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)

    return model, checkpoint["optimizer_state_dict"], checkpoint["epoch"], config
