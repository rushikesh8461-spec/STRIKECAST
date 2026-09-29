from __future__ import annotations

from api.config import Settings
from api.model_loader import ModelLoader, ModelLoadError, RealModel


def test_mock_model_loads_successfully():
    settings = Settings(model_mode="mock", model_version="1.2.3")
    loader = ModelLoader(settings)
    loader.load()
    assert loader.ready is True
    assert loader.load_error is None
    assert loader.model is not None
    assert loader.model.version == "1.2.3"


def test_mock_model_predict_is_deterministic():
    settings = Settings(model_mode="mock")
    loader = ModelLoader(settings)
    loader.load()
    x = {"latitude": 10.0, "longitude": 20.0, "horizon_minutes": 60}
    out1 = loader.model.predict(x)
    out2 = loader.model.predict(x)
    assert out1 == out2
    assert 0.0 <= out1["probability"] <= 1.0


def test_real_model_missing_checkpoint_fails_cleanly():
    settings = Settings(model_mode="real", model_path="/nonexistent/path.pt", model_version="1.0.0")
    loader = ModelLoader(settings)
    loader.load()
    assert loader.ready is False
    assert loader.load_error is not None
    assert loader.model is None


def test_real_model_raises_model_load_error_for_missing_path():
    import pytest

    with pytest.raises(ModelLoadError):
        RealModel(model_path="", version="1.0.0")


def test_real_model_rejects_paths_outside_registry():
    import pytest

    with pytest.raises(ModelLoadError, match="inside MODEL_REGISTRY_DIR"):
        RealModel(model_path="C:/outside/model.pt", version="1.0.0", registry_dir="./trusted")
