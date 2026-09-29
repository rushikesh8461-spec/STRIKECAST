import numpy as np

from src.preprocessing.config import load_config
from src.preprocessing.dataset import build_dataset


def test_build_dataset_is_deterministic_given_same_config_and_input():
    config = load_config()
    bundle_1 = build_dataset(config, demo=True)
    bundle_2 = build_dataset(config, demo=True)

    assert bundle_1.channel_names == bundle_2.channel_names
    assert bundle_1.normalization_stats == bundle_2.normalization_stats
    assert bundle_1.metadata["n_windows"] == bundle_2.metadata["n_windows"]

    for split_name in bundle_1.splits:
        ds1, ds2 = bundle_1.splits[split_name], bundle_2.splits[split_name]
        assert len(ds1) == len(ds2)
        for i in range(len(ds1)):
            s1, s2 = ds1[i], ds2[i]
            np.testing.assert_array_equal(s1["X"], s2["X"])
            np.testing.assert_array_equal(s1["y"], s2["y"])
            np.testing.assert_array_equal(s1["mask"], s2["mask"])


def test_reproducibility_metadata_is_recorded():
    config = load_config()
    bundle = build_dataset(config, demo=True)
    assert bundle.metadata["preprocessing_version"]
    assert bundle.metadata["source_dataset_versions"]
    assert "sequence_length" in bundle.metadata
    assert "split_boundaries" in bundle.metadata
