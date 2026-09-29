import pytest

from packages.strikecast_core.security.model_registry import _resolve_version, validate_model_artifact


def test_rejects_incomplete_candidate(tmp_path):
    with pytest.raises(ValueError, match="missing required files"):
        validate_model_artifact(tmp_path)


@pytest.mark.parametrize("artifact", ["../escape", "C:/escape", "/escape"])
def test_registry_pointer_rejects_traversal(tmp_path, artifact):
    with pytest.raises(ValueError, match="unsafe artifact path"):
        _resolve_version(tmp_path, {"artifact": artifact})
