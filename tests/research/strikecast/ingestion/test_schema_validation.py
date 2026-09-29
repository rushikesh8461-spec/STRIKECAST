import numpy as np

from src.ingestion.contract import VariableSpec
from src.ingestion.validation.schema import validate_schema


def make_vars():
    return [
        VariableSpec("temp", "K", "float32", valid_min=200.0, valid_max=330.0),
        VariableSpec("humidity", "%", "float32", valid_min=0.0, valid_max=100.0),
    ]


def test_valid_schema():
    data = np.stack(
        [np.full((3, 2, 2), 290.0, dtype=np.float32), np.full((3, 2, 2), 50.0, dtype=np.float32)],
        axis=-1,
    )
    result = validate_schema(data, make_vars(), expected_shape_prefix=(3, 2, 2))
    assert result["valid"] is True
    assert result["per_variable"]["temp"]["valid_fraction"] == 1.0


def test_variable_count_mismatch():
    data = np.zeros((3, 2, 2, 3), dtype=np.float32)  # 3 channels, but only 2 variables declared
    result = validate_schema(data, make_vars())
    assert result["valid"] is False
    assert any("mismatch" in i.lower() for i in result["issues"])


def test_out_of_range_values_flagged():
    data = np.stack(
        [np.full((2, 2, 2), 999.0, dtype=np.float32), np.full((2, 2, 2), 50.0, dtype=np.float32)],
        axis=-1,
    )
    result = validate_schema(data, make_vars())
    assert result["valid"] is False
    assert result["per_variable"]["temp"]["valid_fraction"] == 0.0


def test_shape_prefix_mismatch_flagged():
    data = np.zeros((3, 2, 2, 2), dtype=np.float32)
    result = validate_schema(data, make_vars(), expected_shape_prefix=(4, 2, 2))
    assert result["valid"] is False
