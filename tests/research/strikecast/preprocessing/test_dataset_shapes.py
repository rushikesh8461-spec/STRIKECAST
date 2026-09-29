import numpy as np

from src.preprocessing.config import load_config
from src.preprocessing.dataset import build_dataset


def test_dataset_shapes_match_config_and_grid():
    config = load_config()
    bundle = build_dataset(config, demo=True)
    seq_cfg = config.sequence_cfg()
    L, H = seq_cfg["sequence_length"], seq_cfg["forecast_horizon"]
    n_channels = len(bundle.channel_names)

    train_ds = bundle.splits["train"]
    assert len(train_ds) > 0, "expected at least one train window on the bundled demo data"

    sample = train_ds[0]
    n_lat = bundle.metadata["target_grid"]["n_lat"]
    n_lon = bundle.metadata["target_grid"]["n_lon"]

    assert sample["X"].shape == (L, n_lat, n_lon, n_channels)
    assert sample["mask"].shape == (L, n_lat, n_lon, n_channels)
    assert sample["y"].shape == (H, n_lat, n_lon)
    assert not np.isnan(sample["X"]).any(), "final feature tensor must have no NaN left"


def test_dataset_bundle_has_all_three_splits_present_even_if_empty():
    config = load_config()
    bundle = build_dataset(config, demo=True)
    assert set(bundle.splits.keys()) == {"train", "val", "test"}
    for name, ds in bundle.splits.items():
        assert len(ds) == bundle.metadata["n_windows"][name]


def test_feature_and_target_schemas_are_queryable():
    config = load_config()
    bundle = build_dataset(config, demo=True)
    train_ds = bundle.splits["train"]
    schema = train_ds.get_feature_schema()
    assert [f["name"] for f in schema] == bundle.channel_names
    target_schema = train_ds.get_target_schema()
    assert target_schema["dimensions"] == "[forecast_horizon, lat, lon]"
