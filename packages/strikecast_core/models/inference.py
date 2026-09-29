from __future__ import annotations
from dataclasses import dataclass
import json
import hashlib
from ..security.model_registry import _resolve_version, validate_serving_compatibility
from pathlib import Path
import torch
from .runtime_convlstm import ConvLSTMClassifier
from ..security.checkpoints import load_verified_checkpoint

@dataclass(frozen=True)
class ModelPrediction:
    prediction: float
    probability: float
    raw_confidence: float
    model_name: str
    model_version: str
    model_mode: str

class TrainedConvLSTM:
    name="StrikeCast-ConvLSTM-Demo"
    version="1.0.0-trained-demo"
    def __init__(self):
        self.model=ConvLSTMClassifier()
        path=Path(__file__).resolve().parents[3] / "artifacts" / "models" / "demo" / "strikecast_convlstm_demo.pt"
        expected="63150034a809d39a4f60f0003f1de7786d7e9a51457c114adc02a25123ce8cfb"
        expected_metadata={"input_features": 8, "sequence_length": 6, "grid_size": 3,
                           "model_name": self.name, "model_version": self.version}
        checkpoint=load_verified_checkpoint(path, expected, expected_metadata)
        self.model.load_state_dict(checkpoint["state_dict"], strict=True); self.model.eval()
        self.mode="demo"; self.dataset_version="synthetic-demo"; self.feature_schema_version="point-feature-v1"
        self.served_feature_schema_version="strikecast-served-point-v1"

    @classmethod
    def from_registry(cls, registry_dir: str | Path) -> "TrainedConvLSTM":
        """Load only the registry's current pointer; never accepts a checkpoint path."""
        registry=Path(registry_dir).resolve(); pointer_path=registry/"current.json"
        if not pointer_path.is_file(): raise ValueError("registered model pointer is missing")
        pointer=json.loads(pointer_path.read_text(encoding="utf-8"))
        artifact=_resolve_version(registry,pointer)
        validation=validate_serving_compatibility(artifact)
        metadata=json.loads((artifact/"model_metadata.json").read_text(encoding="utf-8"))
        if metadata["model_version"]!=pointer.get("model_version"):
            raise ValueError("registered model version does not match artifact metadata")
        if metadata["model_input_shape"] != [6,8,3,3]: raise ValueError("registered model input shape is incompatible")
        model_obj=cls.__new__(cls); model_obj.model=ConvLSTMClassifier()
        state=torch.load(artifact/"model.pt",map_location="cpu",weights_only=True)
        if not isinstance(state,dict): raise ValueError("registered checkpoint must contain a state dictionary")
        model_obj.model.load_state_dict(state,strict=True); model_obj.model.eval()
        model_obj.name="StrikeCast-ConvLSTM-Candidate"; model_obj.version=validation["model_version"]
        model_obj.mode="candidate"; model_obj.dataset_version=metadata["dataset_version"]
        model_obj.feature_schema_version=metadata["feature_schema_version"]
        model_obj.served_feature_schema_version=metadata["served_feature_schema_version"]
        model_obj.artifact_sha256=hashlib.sha256((artifact/"model.pt").read_bytes()).hexdigest()
        return model_obj
    def predict(self, sequence):
        values = torch.as_tensor(sequence, dtype=torch.float32)
        if tuple(values.shape) != (6, 3, 3, 8) or not torch.isfinite(values).all():
            raise ValueError("demo model input must be finite [T=6,H=3,W=3,C=8]")
        # sequence is [T][H][W][C] -> [1,T,C,H,W]
        x = values.permute(0, 3, 1, 2).unsqueeze(0)
        with torch.no_grad():
            logit=float(self.model(x)[0]); p=float(torch.sigmoid(torch.tensor(logit)))
        confidence=max(0.55,min(0.97,0.72+0.18*abs(p-0.5)*2))
        return ModelPrediction(round(p*100,2),round(p,4),round(confidence,4),self.name,self.version,getattr(self,"mode","demo"))
