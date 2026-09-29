from src.features.schema import resolve_channel_order
from src.preprocessing.config import load_config
from src.preprocessing.dataset import build_dataset


def test_built_dataset_channel_order_matches_schema_contract():
    config = load_config()
    bundle = build_dataset(config, demo=True)
    expected = resolve_channel_order(config.features_cfg()["enabled_derived_features"])
    assert bundle.channel_names == expected


def test_built_dataset_channel_order_is_stable_across_runs():
    config = load_config()
    bundle_1 = build_dataset(config, demo=True)
    bundle_2 = build_dataset(config, demo=True)
    assert bundle_1.channel_names == bundle_2.channel_names
