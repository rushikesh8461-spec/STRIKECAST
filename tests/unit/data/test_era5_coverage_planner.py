import importlib.util
from pathlib import Path
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/data/plan_required_era5.py"
SPEC = importlib.util.spec_from_file_location("coverage_planner", SCRIPT)
PLANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLANNER)


@pytest.mark.parametrize("name", ["../escape.grib", "C:/escape.grib", "/absolute.grib", "dir\\escape.grib"])
def test_rejects_unsafe_zip_member_paths(name):
    info = zipfile.ZipInfo(name)
    info.filename = name
    with pytest.raises(ValueError, match="unsafe archive member"):
        PLANNER.validate_zip_info(info, 0)


def test_rejects_expansion_ratio_and_total_limits(monkeypatch):
    info = zipfile.ZipInfo("file.grib")
    info.file_size = 2000
    info.compress_size = 1
    with pytest.raises(ValueError, match="expansion ratio"):
        PLANNER.validate_zip_info(info, 0)
    monkeypatch.setattr(PLANNER, "MAX_RATIO", 5000)
    monkeypatch.setattr(PLANNER, "MAX_EXPANDED_BYTES", 1000)
    with pytest.raises(ValueError, match="total expanded"):
        PLANNER.validate_zip_info(info, 0)
