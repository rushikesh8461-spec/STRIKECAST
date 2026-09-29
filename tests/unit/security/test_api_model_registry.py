"""API model loading is registry-pointer-only and rejects incompatibility pre-load."""
import hashlib
import json

import pytest
import torch

from strikecast_core.models.inference import TrainedConvLSTM
from strikecast_core.models.runtime_convlstm import ConvLSTMClassifier
from strikecast_core.security.model_registry import REQUIRED, validate_serving_compatibility


def _registered_model(tmp_path, *, feature_schema="point-feature-v1"):
    registry=tmp_path/"registry"; artifact=registry/"versions"/"candidate-v1"; artifact.mkdir(parents=True)
    torch.save(ConvLSTMClassifier().state_dict(),artifact/"model.pt")
    metadata={"model_version":"candidate-v1","architecture":"ConvLSTMClassifier","schema_version":feature_schema,
      "feature_schema_version":feature_schema,"served_feature_schema_version":"strikecast-served-point-v1",
      "normalization_version":"point-feature-minmax-v1","dataset_version":"fixture-v1","model_input_shape":[6,8,3,3]}
    (artifact/"model_metadata.json").write_text(json.dumps(metadata),encoding="utf-8")
    json_files={"dataset_manifest.json":{"dataset_version":"fixture-v1"},"feature_schema.json":{"schema_version":feature_schema},
      "target_schema.json":{"schema_version":"target-v1"},"normalization.json":{"normalization_version":"point-feature-minmax-v1"},
      "metrics.json":{"status":"fixture-only"},"calibration.json":{"fit_split":"validation"}}
    for name,value in json_files.items(): (artifact/name).write_text(json.dumps(value),encoding="utf-8")
    (artifact/"training_config.yaml").write_text("fixture: true\n",encoding="utf-8")
    (artifact/"model_card.md").write_text("fixture only\n",encoding="utf-8")
    lines=[]
    for name in sorted(REQUIRED-{"checksums.sha256"}):
        lines.append(f"{hashlib.sha256((artifact/name).read_bytes()).hexdigest()}  {name}")
    (artifact/"checksums.sha256").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (registry/"current.json").write_text(json.dumps({"artifact":"versions/candidate-v1","model_version":"candidate-v1"}),encoding="utf-8")
    return registry,artifact


def test_valid_registered_candidate_loads_safely(tmp_path):
    registry,artifact=_registered_model(tmp_path)
    assert validate_serving_compatibility(artifact)["api_compatibility"]=="SUPPORTED"
    model=TrainedConvLSTM.from_registry(registry)
    result=model.predict([[[[0.5]*8 for _ in range(3)] for _ in range(3)] for _ in range(6)])
    assert result.model_mode=="candidate" and model.dataset_version=="fixture-v1"


def test_registry_loader_rejects_unregistered_corrupt_and_wrong_schema(tmp_path):
    with pytest.raises(ValueError,match="pointer"):
        TrainedConvLSTM.from_registry(tmp_path/"empty")
    registry,artifact=_registered_model(tmp_path/"corrupt")
    with (artifact/"model.pt").open("ab") as stream: stream.write(b"tamper")
    with pytest.raises(ValueError,match="checksum"):
        TrainedConvLSTM.from_registry(registry)
    registry,artifact=_registered_model(tmp_path/"wrong",feature_schema="wrong-schema")
    with pytest.raises(ValueError,match="INFERENCE_COMPATIBILITY"):
        TrainedConvLSTM.from_registry(registry)


def test_wrong_checksum_and_unsafe_registry_pointer_rejected(tmp_path):
    registry,artifact=_registered_model(tmp_path/"checksum")
    (artifact/"checksums.sha256").write_text("0"*64+"  model.pt\n",encoding="utf-8")
    with pytest.raises(ValueError,match="checksum"):
        TrainedConvLSTM.from_registry(registry)
    registry.mkdir(parents=True,exist_ok=True)
    (registry/"current.json").write_text(json.dumps({"artifact":"../outside","model_version":"x"}),encoding="utf-8")
    with pytest.raises(ValueError,match="unsafe"):
        TrainedConvLSTM.from_registry(registry)
