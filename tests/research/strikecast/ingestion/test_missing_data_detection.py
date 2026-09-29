import numpy as np

from src.ingestion.validation.quality import compute_missing_fraction


def test_no_missing_values():
    data = np.ones((10, 10), dtype=np.float32)
    assert compute_missing_fraction(data) == 0.0


def test_all_nan():
    data = np.full((5, 5), np.nan, dtype=np.float32)
    assert compute_missing_fraction(data) == 1.0


def test_partial_nan():
    data = np.ones((10,), dtype=np.float32)
    data[:3] = np.nan
    assert abs(compute_missing_fraction(data) - 0.3) < 1e-9


def test_sentinel_counted_as_missing():
    data = np.array([1.0, 2.0, -9999.0, 3.0], dtype=np.float32)
    frac = compute_missing_fraction(data, sentinel=-9999.0)
    assert abs(frac - 0.25) < 1e-9


def test_empty_array_is_fully_missing():
    data = np.array([], dtype=np.float32)
    assert compute_missing_fraction(data) == 1.0
