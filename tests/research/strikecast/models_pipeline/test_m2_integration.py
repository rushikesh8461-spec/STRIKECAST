"""
Tests that M2 (src/preprocessing) and M3 (src/models, src/training,
src/inference) actually talk to each other, end to end, on the bundled
data/sample_demo data — not just that each half's own synthetic-data tests
pass in isolation.
"""

import os
import tempfile

import pytest

torch = pytest.importorskip("torch")

from ml.training.strikecast_training.m2_bridge import (  # noqa: E402
    channel_groups_by_source,
    load_m2_bundle,
    build_m2_dataset,
)
from ml.training.strikecast_training.config import Config, DataContract, TrainConfig  # noqa: E402


def test_channel_groups_by_source_groups_base_and_derived_together():
    """Pure logic test (no M2/torch data needed): a base feature and its
    "<source> (derived)" counterpart must land in the same group, and group
    order follows first appearance."""
    schema = [
        {"name": "brightness_temperature", "source": "satellite"},
        {"name": "reflectivity", "source": "radar"},
        {"name": "lightning_strike_count", "source": "lightning"},
        {"name": "reflectivity_dt", "source": "radar (derived)"},
        {"name": "brightness_temperature_dt", "source": "satellite (derived)"},
    ]
    groups = channel_groups_by_source(schema)
    assert list(groups.keys()) == ["satellite", "radar", "lightning"]
    assert groups["satellite"] == [0, 4]
    assert groups["radar"] == [1, 3]
    assert groups["lightning"] == [2]


def test_m2_bundle_matches_documented_demo_shapes():
    """Sanity check against docs/m2_m3_contract.md's stated demo numbers,
    so a future change to the demo data or config is caught here."""
    bundle = load_m2_bundle(demo=True)
    assert bundle.metadata["target_grid"]["n_lat"] == 17
    assert bundle.metadata["target_grid"]["n_lon"] == 17
    assert len(bundle.channel_names) == 19
    assert len(bundle.splits["train"]) > 0  # the known-empty split is val/test, not train
    assert bundle.metadata["split_version"] == "chronological-whole-window-v1"
    ranges = bundle.metadata["split_time_ranges"]
    assert ranges["train"]["window_count"] == len(bundle.splits["train"])
    assert ranges["val"]["first_input_time"] is None
    if ranges["val"]["window_count"]:
        assert ranges["train"]["last_target_time"] < ranges["val"]["first_input_time"]


def test_m2_dataset_single_tensor_shapes_match_contract():
    bundle = load_m2_bundle(demo=True)
    contract = DataContract.from_m2_bundle(bundle, multimodal=False)
    ds = build_m2_dataset(bundle.splits["train"], contract, multimodal=False)

    x, y = ds[0]
    assert tuple(x.shape) == (contract.sequence_length, contract.input_channels,
                               contract.height, contract.width)
    assert tuple(y.shape) == (contract.forecast_horizon, 1, contract.height, contract.width)
    assert x.dtype == contract.dtype
    # y is a binary occurrence target at the default M2 config
    assert set(torch.unique(y).tolist()) <= {0.0, 1.0}
    lightning_index = bundle.channel_names.index("lightning_strike_count")
    lightning_stats = bundle.normalization_stats["lightning_strike_count"]
    assert contract.input_channel_names == bundle.channel_names
    assert contract.lightning_channel_index == lightning_index
    assert contract.lightning_zero_threshold == pytest.approx(-lightning_stats["mean"] / lightning_stats["std"])


def test_m2_multimodal_dataset_shapes_match_contract():
    bundle = load_m2_bundle(demo=True)
    contract = DataContract.from_m2_bundle(bundle, multimodal=True)
    ds = build_m2_dataset(bundle.splits["train"], contract, multimodal=True)

    x, y = ds[0]
    assert isinstance(x, dict)
    assert set(x.keys()) == set(contract.modalities)
    for m in contract.modalities:
        c_m = contract.modality_channels[m]
        assert tuple(x[m].shape) == (contract.sequence_length, c_m, contract.height, contract.width)
    # channel counts across modalities must add back up to the full channel count
    assert sum(contract.modality_channels.values()) == len(bundle.channel_names)


def test_train_convlstm_end_to_end_on_real_m2_data():
    """The actual integration smoke test: train ConvLSTM on real M2 windows
    (not SyntheticDataset), save a checkpoint, reload it, and run inference
    on a real M2 sample — proving the M2 -> M3 path works, not just that
    each side works in isolation."""
    from ml.training.strikecast_training.train import train_nn_model
    from ml.training.strikecast_training.checkpoint import load_checkpoint
    from src.inference.predict import run_inference_nn

    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(
            data=DataContract(),  # placeholder; replaced by build_dataloaders() from the m2 bundle
            train=TrainConfig(
                seed=42, batch_size=2, epochs=1, checkpoint_dir=tmp_dir,
                conv_hidden_dims=[4], checkpoint_every_n_epochs=1,
                data_source="m2", m2_demo=True,
            ),
        )
        ckpt_path = train_nn_model(config, "convlstm")
        assert ckpt_path is not None and os.path.exists(ckpt_path)

        model, _, epoch, loaded_config = load_checkpoint(ckpt_path)
        assert epoch == 1
        assert loaded_config.train.data_source == "m2"
        # the contract saved in the checkpoint is the REAL m2-derived one,
        # not the DataContract() placeholder passed in above
        assert loaded_config.data.height == 17
        assert loaded_config.data.width == 17
        assert loaded_config.data.input_channels == 19

        output = run_inference_nn(ckpt_path, data_source="m2", split="test")
        assert tuple(output.prediction.shape) == (1, 1, 1, 17, 17)


def test_train_fusion_convlstm_end_to_end_on_real_m2_data():
    from ml.training.strikecast_training.train import train_nn_model
    from ml.training.strikecast_training.checkpoint import load_checkpoint

    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(
            data=DataContract(),
            train=TrainConfig(
                seed=42, batch_size=2, epochs=1, checkpoint_dir=tmp_dir,
                conv_hidden_dims=[4], checkpoint_every_n_epochs=1,
                data_source="m2", m2_demo=True,
            ),
        )
        ckpt_path = train_nn_model(config, "fusion_convlstm")
        assert ckpt_path is not None and os.path.exists(ckpt_path)

        model, _, _, loaded_config = load_checkpoint(ckpt_path)
        assert len(loaded_config.data.modalities) >= 2
        assert model.model_name == "fusion_convlstm"


def test_val_split_empty_on_demo_data_is_handled_not_crashed():
    """Documented limitation (docs/m2_m3_contract.md): bundled demo data has
    0 val windows. Training must skip validation rather than divide by zero."""
    from ml.training.strikecast_training.train import train_nn_model

    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(
            data=DataContract(),
            train=TrainConfig(
                seed=1, batch_size=2, epochs=1, checkpoint_dir=tmp_dir,
                conv_hidden_dims=[4], data_source="m2", m2_demo=True,
            ),
        )
        ckpt_path = train_nn_model(config, "convlstm")  # must not raise
        assert os.path.exists(ckpt_path)
