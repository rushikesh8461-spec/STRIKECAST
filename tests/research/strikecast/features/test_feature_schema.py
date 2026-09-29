import pytest

from src.features.schema import (
    BASE_FEATURES,
    DERIVED_FEATURES,
    get_feature_schema,
    resolve_channel_order,
)


def test_base_features_always_included_regardless_of_derived_config():
    order = resolve_channel_order(enabled_derived_features=[])
    base_names = [f.name for f in BASE_FEATURES]
    assert order == base_names


def test_enabled_derived_features_appended_in_declared_order_not_config_order():
    # config lists them in a different order than DERIVED_FEATURES declares
    derived_declared_order = [f.name for f in DERIVED_FEATURES]
    shuffled_config_order = list(reversed(derived_declared_order))
    order = resolve_channel_order(enabled_derived_features=shuffled_config_order)
    base_names = [f.name for f in BASE_FEATURES]
    assert order == base_names + derived_declared_order


def test_disabled_derived_features_excluded():
    one_feature = DERIVED_FEATURES[0].name
    order = resolve_channel_order(enabled_derived_features=[one_feature])
    assert order == [f.name for f in BASE_FEATURES] + [one_feature]


def test_unknown_derived_feature_raises():
    with pytest.raises(ValueError):
        resolve_channel_order(enabled_derived_features=["not_a_real_feature"])


def test_every_feature_has_complete_documentation():
    for f in BASE_FEATURES + DERIVED_FEATURES:
        assert f.name and f.source and f.formula and f.units and f.dimensions and f.why


def test_get_feature_schema_matches_resolve_channel_order():
    enabled = [DERIVED_FEATURES[0].name]
    schema = get_feature_schema(enabled)
    order = resolve_channel_order(enabled)
    assert [entry["name"] for entry in schema] == order


def test_no_duplicate_feature_names_across_base_and_derived():
    names = [f.name for f in BASE_FEATURES] + [f.name for f in DERIVED_FEATURES]
    assert len(names) == len(set(names))
