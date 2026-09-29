import torch
import pytest

from ml.training.strikecast_training.config import DataContract
from ml.training.strikecast_training.dataset import SyntheticDataset
from src.models.persistence import PersistenceBaseline
from src.models.climatology import ClimatologyBaseline
from src.models.classical_ml import ClassicalMLBaseline
from src.models.tree_ml import TreeMLBaseline
from src.models.convlstm import ConvLSTM
from src.models.fusion import FusionConvLSTM


def tiny_contract(**overrides) -> DataContract:
    defaults = dict(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1,
                    input_channel_names=["lightning_strike_count"], lightning_channel_index=0,
                    lightning_zero_threshold=0.0)
    defaults.update(overrides)
    return DataContract(**defaults)


def test_model_import():
    # If any of these fail to import, this test fails loudly.
    assert PersistenceBaseline is not None
    assert ClimatologyBaseline is not None
    assert ClassicalMLBaseline is not None
    assert TreeMLBaseline is not None
    assert ConvLSTM is not None
    assert FusionConvLSTM is not None


def test_persistence_forward_and_output_shape():
    contract = tiny_contract()
    model = PersistenceBaseline(contract)
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    x = x.unsqueeze(0)  # add batch dim -> [1,T,C,H,W]

    output = model.predict(x)
    expected_shape = contract.target_shape(batch_size=1)
    assert tuple(output.prediction.shape) == expected_shape
    assert output.model_name == "persistence"
    # binary target -> values must be probabilities in [0,1]
    assert torch.all(output.prediction >= 0) and torch.all(output.prediction <= 1)


def test_binary_persistence_uses_named_lightning_channel_and_zero_threshold():
    contract = tiny_contract(input_channels=2, input_channel_names=["temperature", "lightning_strike_count"],
                            lightning_channel_index=1, lightning_zero_threshold=-0.25)
    model = PersistenceBaseline(contract)
    x = torch.zeros((1, 3, 2, 8, 8))
    x[:, :, 0] = 100.0  # must never be mistaken for the lightning signal
    x[:, -1, 1, :4] = 0.0
    x[:, -1, 1, 4:] = -0.5
    prediction = model.predict(x).prediction
    assert torch.all(prediction[:, :, :, :4] == 1)
    assert torch.all(prediction[:, :, :, 4:] == 0)


def test_binary_persistence_requires_explicit_lightning_channel():
    contract = tiny_contract(input_channel_names=None, lightning_channel_index=None, lightning_zero_threshold=None)
    with pytest.raises(ValueError, match="requires the named lightning_strike_count"):
        PersistenceBaseline(contract)


def test_climatology_is_fitted_from_train_labels_only_and_broadcasts():
    contract = tiny_contract(height=2, width=2)
    model = ClimatologyBaseline(contract)
    labels = torch.tensor([
        [[[[1.0, 0.0], [0.0, 0.0]]]],
        [[[[1.0, 1.0], [0.0, 0.0]]]],
    ])
    model.fit(labels)
    x = torch.zeros((3, 3, 1, 2, 2))
    predicted = model.predict(x).prediction
    assert tuple(predicted.shape) == (3, 1, 1, 2, 2)
    assert torch.allclose(predicted[:, 0, 0], torch.tensor([[[1.0, 0.5], [0.0, 0.0]]] * 3))


def test_climatology_rejects_prediction_before_train_fit():
    model = ClimatologyBaseline(tiny_contract())
    with pytest.raises(RuntimeError, match="fit on TRAIN labels"):
        model.predict(torch.zeros((1, 3, 1, 8, 8)))


def test_tree_baseline_fits_and_returns_binary_probabilities():
    contract = tiny_contract()
    model = TreeMLBaseline(contract)
    ds = SyntheticDataset(contract, num_samples=16, seed=3)
    x = torch.stack([ds[index][0] for index in range(len(ds))])
    y = torch.stack([ds[index][1] for index in range(len(ds))])
    model.fit(x, y)
    output = model.predict(x[:2])
    assert output.model_name == "tree_ml"
    assert tuple(output.prediction.shape) == contract.target_shape(2)
    assert torch.isfinite(output.prediction).all()
    assert torch.all((output.prediction >= 0) & (output.prediction <= 1))


def test_classical_ml_fit_predict_shape():
    contract = tiny_contract()
    model = ClassicalMLBaseline(contract)
    ds = SyntheticDataset(contract, num_samples=16, seed=0)
    from torch.utils.data import DataLoader
    loader = DataLoader(ds, batch_size=16)
    xb, yb = next(iter(loader))

    model.fit(xb, yb)
    output = model.predict(xb)
    expected_shape = contract.target_shape(batch_size=16)
    assert tuple(output.prediction.shape) == expected_shape
    assert output.model_name == "classical_ml"


def test_classical_ml_predict_before_fit_raises():
    contract = tiny_contract()
    model = ClassicalMLBaseline(contract)
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    with pytest.raises(RuntimeError):
        model.predict(x.unsqueeze(0))


def test_convlstm_forward_shape():
    contract = tiny_contract()
    model = ConvLSTM(contract, hidden_dims=[4, 4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    x = x.unsqueeze(0)

    out = model(x)
    expected_shape = contract.target_shape(batch_size=1)
    assert tuple(out.shape) == expected_shape
    # binary -> sigmoid applied -> bounded [0,1]
    assert torch.all(out >= 0) and torch.all(out <= 1)


def test_convlstm_predict_schema():
    contract = tiny_contract()
    model = ConvLSTM(contract, hidden_dims=[4, 4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    output = model.predict(x.unsqueeze(0))
    assert output.model_name == "convlstm"
    assert output.model_version == ConvLSTM.model_version
    assert tuple(output.prediction.shape) == contract.target_shape(batch_size=1)


def test_convlstm_multistep_horizon():
    contract = tiny_contract(forecast_horizon=3)
    model = ConvLSTM(contract, hidden_dims=[4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    out = model(x.unsqueeze(0))
    assert tuple(out.shape) == contract.target_shape(batch_size=1)
    assert out.shape[1] == 3  # T_out


def test_convlstm_continuous_target_no_sigmoid():
    contract = tiny_contract(target_type="continuous")
    model = ConvLSTM(contract, hidden_dims=[4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    out = model(x.unsqueeze(0))
    assert tuple(out.shape) == contract.target_shape(batch_size=1)
    # continuous outputs are NOT bounded to [0,1] (no sigmoid) — just check
    # the tensor is finite and shaped correctly.
    assert torch.isfinite(out).all()


def test_fusion_requires_multiple_modalities():
    contract = tiny_contract()  # only 1 modality by default
    with pytest.raises(ValueError):
        FusionConvLSTM(contract)


def test_fusion_forward_shape():
    contract = tiny_contract(
        modalities=["radar", "satellite"],
        modality_channels={"radar": 1, "satellite": 2},
    )
    model = FusionConvLSTM(contract, encoder_hidden_dims=[4, 4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]  # dict of modality -> [T,C,H,W]
    x_batched = {k: v.unsqueeze(0) for k, v in x.items()}

    out = model(x_batched)
    expected_shape = contract.target_shape(batch_size=1)
    assert tuple(out.shape) == expected_shape


def test_fusion_predict_schema():
    contract = tiny_contract(
        modalities=["radar", "satellite"],
        modality_channels={"radar": 1, "satellite": 2},
    )
    model = FusionConvLSTM(contract, encoder_hidden_dims=[4, 4])
    ds = SyntheticDataset(contract, num_samples=2, seed=0)
    x, _ = ds[0]
    x_batched = {k: v.unsqueeze(0) for k, v in x.items()}
    output = model.predict(x_batched)
    assert output.model_name == "fusion_convlstm"
    assert tuple(output.prediction.shape) == contract.target_shape(batch_size=1)


def test_fusion_rejects_non_dict_input():
    contract = tiny_contract(
        modalities=["radar", "satellite"],
        modality_channels={"radar": 1, "satellite": 2},
    )
    model = FusionConvLSTM(contract, encoder_hidden_dims=[4, 4])
    bad_input = torch.randn(1, 3, 1, 8, 8)
    with pytest.raises(TypeError):
        model(bad_input)
