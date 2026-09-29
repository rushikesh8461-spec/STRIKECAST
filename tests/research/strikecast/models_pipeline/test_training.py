import os
import tempfile
import torch
from torch.utils.data import DataLoader

from ml.training.strikecast_training.config import Config, DataContract, TrainConfig
from ml.training.strikecast_training.dataset import SyntheticDataset
from ml.training.strikecast_training.checkpoint import save_checkpoint, load_checkpoint
from ml.training.strikecast_training.train import train_nn_model, train_classical
from src.models.factory import build_model
from src.models.classical_ml import ClassicalMLBaseline


def tiny_config(tmp_dir: str, model_name_hidden_dims=(4,)) -> Config:
    data = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1)
    train = TrainConfig(
        seed=42, batch_size=2, epochs=1, checkpoint_dir=tmp_dir,
        conv_hidden_dims=list(model_name_hidden_dims), checkpoint_every_n_epochs=1,
    )
    return Config(data=data, train=train)


def test_dataset_contract_shapes():
    contract = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1)
    ds = SyntheticDataset(contract, num_samples=8, seed=0)
    loader = DataLoader(ds, batch_size=4)
    xb, yb = next(iter(loader))
    assert tuple(xb.shape) == contract.input_shape(4)
    assert tuple(yb.shape) == contract.target_shape(4)


def test_training_smoke_convlstm():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        ckpt_path = train_nn_model(config, "convlstm")
        assert ckpt_path is not None
        assert os.path.exists(ckpt_path)


def test_checkpoint_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        model = build_model("convlstm", config.data, config.train)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        ckpt_path = os.path.join(tmp_dir, "test_ckpt.pt")
        save_checkpoint(model, optimizer, epoch=1, config=config, path=ckpt_path)
        assert os.path.exists(ckpt_path)

        loaded_model, opt_state, epoch, loaded_config = load_checkpoint(ckpt_path)
        assert epoch == 1
        assert loaded_config.data.height == config.data.height
        assert loaded_model.model_name == model.model_name

        # Reload test: same input -> identical output between original and
        # reloaded model (weights round-tripped exactly).
        ds = SyntheticDataset(config.data, num_samples=1, seed=99)
        x, _ = ds[0]
        x = x.unsqueeze(0)

        model.eval()
        loaded_model.eval()
        with torch.no_grad():
            out_original = model(x)
            out_reloaded = loaded_model(x)

        assert torch.allclose(out_original, out_reloaded, atol=1e-6)


def test_classical_ml_training_and_checkpoint():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        path = train_classical(config)
        assert os.path.exists(path)

        reloaded = ClassicalMLBaseline.load(path)
        ds = SyntheticDataset(config.data, num_samples=2, seed=1)
        x, _ = ds[0]
        output = reloaded.predict(x.unsqueeze(0))
        assert tuple(output.prediction.shape) == config.data.target_shape(1)
