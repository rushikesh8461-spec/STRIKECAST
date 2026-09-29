import tempfile
import torch

from ml.training.strikecast_training.config import Config, DataContract, TrainConfig
from ml.training.strikecast_training.seed import set_seed
from ml.training.strikecast_training.dataset import SyntheticDataset
from src.models.factory import build_model


def tiny_config(tmp_dir: str) -> Config:
    data = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1)
    train = TrainConfig(seed=123, batch_size=2, epochs=1, checkpoint_dir=tmp_dir, conv_hidden_dims=[4])
    return Config(data=data, train=train)


def test_seed_reproducibility_model_init():
    """Same seed -> identical model initialization (weights)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)

        set_seed(config.train.seed)
        model_a = build_model("convlstm", config.data, config.train)

        set_seed(config.train.seed)
        model_b = build_model("convlstm", config.data, config.train)

        for p_a, p_b in zip(model_a.parameters(), model_b.parameters()):
            assert torch.allclose(p_a, p_b)


def test_seed_reproducibility_synthetic_dataset():
    """Same seed -> identical synthetic dataset content."""
    contract = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1)
    ds_a = SyntheticDataset(contract, num_samples=4, seed=7)
    ds_b = SyntheticDataset(contract, num_samples=4, seed=7)

    for i in range(4):
        xa, ya = ds_a[i]
        xb, yb = ds_b[i]
        assert torch.allclose(xa, xb)
        assert torch.allclose(ya, yb)


def test_seed_reproducibility_full_forward_pass():
    """Same seed end-to-end (init + data) -> identical model output."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)

        def run():
            set_seed(config.train.seed)
            model = build_model("convlstm", config.data, config.train)
            model.eval()
            ds = SyntheticDataset(config.data, num_samples=1, seed=config.train.seed)
            x, _ = ds[0]
            with torch.no_grad():
                return model(x.unsqueeze(0))

        out_a = run()
        out_b = run()
        assert torch.allclose(out_a, out_b)
