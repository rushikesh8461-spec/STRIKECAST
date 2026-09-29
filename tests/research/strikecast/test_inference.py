import os
import tempfile
import torch

from ml.training.strikecast_training.config import Config, DataContract, TrainConfig
from ml.training.strikecast_training.train import train_nn_model, train_classical
from src.inference.predict import (
    run_inference_nn,
    run_inference_classical,
    run_inference_persistence,
)
from src.models.schema import ModelOutput


def tiny_config(tmp_dir: str) -> Config:
    data = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1)
    train = TrainConfig(seed=42, batch_size=2, epochs=1, checkpoint_dir=tmp_dir, conv_hidden_dims=[4])
    return Config(data=data, train=train)


def test_inference_convlstm_end_to_end():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        ckpt_path = train_nn_model(config, "convlstm")

        output = run_inference_nn(ckpt_path)
        assert isinstance(output, ModelOutput)
        assert tuple(output.prediction.shape) == config.data.target_shape(1)


def test_inference_schema_fields_present():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        ckpt_path = train_nn_model(config, "convlstm")
        output = run_inference_nn(ckpt_path)

        d = output.as_dict()
        for key in ["prediction", "model_name", "model_version", "timestamps", "metadata"]:
            assert key in d


def test_inference_classical_ml_end_to_end():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = tiny_config(tmp_dir)
        path = train_classical(config)
        output = run_inference_classical(path)
        assert isinstance(output, ModelOutput)
        assert tuple(output.prediction.shape) == config.data.target_shape(1)


def test_inference_persistence_no_checkpoint_needed():
    data_contract = DataContract(sequence_length=3, input_channels=1, height=8, width=8, forecast_horizon=1,
                                 input_channel_names=["lightning_strike_count"], lightning_channel_index=0,
                                 lightning_zero_threshold=0.0)
    output = run_inference_persistence(data_contract)
    assert isinstance(output, ModelOutput)
    assert tuple(output.prediction.shape) == data_contract.target_shape(1)
