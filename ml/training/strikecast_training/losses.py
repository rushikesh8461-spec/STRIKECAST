"""
Loss selection. Kept separate from train.py so swapping the loss for a
given target_type doesn't require touching the training loop.

Registry keys match TrainConfig.loss strings.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.training.strikecast_training.config import DataContract


_REGISTRY = {
    "bce": nn.BCELoss,        # expects probabilities in [0,1] (model already applies sigmoid)
    "mse": nn.MSELoss,        # continuous regression
    "ce": nn.CrossEntropyLoss,  # multiclass, expects raw logits
}


def masked_binary_cross_entropy(probabilities: torch.Tensor, targets: torch.Tensor,
                                observation_mask: torch.Tensor) -> torch.Tensor:
    """BCE over observed target cells only; UNKNOWN cells contribute no loss."""
    if probabilities.shape != targets.shape or targets.shape != observation_mask.shape:
        raise ValueError("probabilities, targets, and observation_mask must have identical shapes")
    mask = observation_mask.to(dtype=torch.bool)
    if not torch.isfinite(probabilities).all() or not torch.isfinite(targets).all():
        raise ValueError("probabilities and target storage values must be finite")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("probabilities must be in [0, 1]")
    if not torch.isin(targets[mask], torch.tensor([0.0, 1.0], device=targets.device, dtype=targets.dtype)).all():
        raise ValueError("observed binary targets must be 0 or 1")
    if not mask.any():
        raise ValueError("batch contains no observed target cells; refusing an all-UNKNOWN loss")
    elementwise = F.binary_cross_entropy(probabilities, targets, reduction="none")
    return elementwise[mask].mean()


def get_loss(name: str, contract: DataContract):
    if name not in _REGISTRY:
        raise ValueError(f"Unknown loss '{name}'. Available: {list(_REGISTRY.keys())}")

    # Guard against mismatched loss/target_type combinations — this is
    # exactly the kind of silent bug Phase 10 warns about.
    expected = {
        "binary": "bce",
        "continuous": "mse",
        "multiclass": "ce",
    }
    if expected[contract.target_type] != name:
        raise ValueError(
            f"Loss '{name}' does not match target_type='{contract.target_type}' "
            f"(expected '{expected[contract.target_type]}'). "
            f"Update TrainConfig.loss or DataContract.target_type."
        )

    return _REGISTRY[name]()
