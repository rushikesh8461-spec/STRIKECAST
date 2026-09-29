import pytest
import torch

from ml.training.strikecast_training.losses import masked_binary_cross_entropy


def test_unknown_target_cells_do_not_contribute_to_binary_loss():
    probabilities = torch.tensor([0.2, 0.9, 0.7])
    targets = torch.tensor([0.0, 1.0, 0.0])
    observed = torch.tensor([True, True, False])
    loss = masked_binary_cross_entropy(probabilities, targets, observed)
    expected = torch.nn.functional.binary_cross_entropy(probabilities[:2], targets[:2])
    assert torch.isclose(loss, expected)


def test_masked_binary_loss_rejects_all_unknown_batch():
    with pytest.raises(ValueError, match="no observed target cells"):
        masked_binary_cross_entropy(torch.tensor([0.2]), torch.tensor([0.0]), torch.tensor([False]))
