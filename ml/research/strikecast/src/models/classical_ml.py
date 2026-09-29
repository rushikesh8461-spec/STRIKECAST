"""
Classical ML baseline.

Approach: treat every spatial cell as an independent sample. For each
pixel, the feature vector is its own temporal history (flattened
T*C values at that pixel); the label is that pixel's target value.
A single shared scikit-learn estimator is fit across all (batch * H * W)
pixel-samples. This ignores spatial context (deliberately — it's the
"defensible simple baseline", not a competitor to ConvLSTM) but does use
temporal history per cell.

target_type == "binary"   -> LogisticRegression (per-pixel probability)
target_type == "continuous" -> LinearRegression
target_type == "multiclass" -> not implemented yet (see PersistenceBaseline
                                docstring for the same reasoning)

This baseline does NOT go through the torch training loop — it has its own
fit()/predict() via sklearn, exposed through the same BaseForecastModel
interface so training/train.py and inference/predict.py can treat it
uniformly.
"""

from typing import Optional
import os
import joblib
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression, LinearRegression

from src.models.base import BaseForecastModel
from src.models.schema import ModelOutput
from ml.training.strikecast_training.config import DataContract


class ClassicalMLBaseline(BaseForecastModel):
    model_name = "classical_ml"
    model_version = "1.0.0"

    def __init__(self, contract: DataContract, seed: int = 0):
        super().__init__(contract)
        if contract.target_type == "multiclass":
            raise NotImplementedError(
                "ClassicalMLBaseline has no defined behavior for "
                "target_type='multiclass' yet — extend once confirmed."
            )
        if contract.forecast_horizon != 1:
            raise NotImplementedError(
                "ClassicalMLBaseline currently supports forecast_horizon=1 "
                "only (a single shared estimator per horizon step). "
                "Multi-step horizon would need one estimator per step or a "
                "sequence-aware classical model — not yet implemented."
            )

        self._estimator = (
            LogisticRegression(max_iter=200, random_state=seed)
            if contract.target_type == "binary"
            else LinearRegression()
        )
        self._fitted = False

    def trainable(self) -> bool:
        return False  # fit() is called explicitly, not via the torch loop

    def _flatten_features(self, x: torch.Tensor) -> np.ndarray:
        """x: [B,T,C,H,W] -> features: [B*H*W, T*C]"""
        if isinstance(x, dict):
            x = x[self.contract.modalities[0]]
        B, T, C, H, W = x.shape
        # -> [B, H, W, T, C] -> [B*H*W, T*C]
        x = x.permute(0, 3, 4, 1, 2).reshape(B * H * W, T * C)
        return x.detach().cpu().numpy()

    def fit(self, x: torch.Tensor, y: torch.Tensor, observation_mask: torch.Tensor | None = None):
        """x: [B,T,C,H,W], y: [B,1,1,H,W] (forecast_horizon=1, C_out=1)"""
        features = self._flatten_features(x)
        B, T_out, C_out, H, W = y.shape
        labels_tensor = y.permute(0, 3, 4, 1, 2).reshape(B * H * W)
        if observation_mask is not None:
            mask = torch.as_tensor(observation_mask, dtype=torch.bool, device=y.device)
            if mask.shape != y.shape:
                raise ValueError("observation_mask must match y")
            keep = mask.permute(0, 3, 4, 1, 2).reshape(B * H * W)
            features = features[keep.detach().cpu().numpy()]
            labels_tensor = labels_tensor[keep]
        labels = labels_tensor.detach().cpu().numpy()
        if labels.size == 0:
            raise ValueError("No observed target labels available for classical model fitting")
        if self.contract.target_type == "binary":
            labels = labels.astype(int)
        self._estimator.fit(features, labels)
        self._fitted = True
        return self

    def predict(self, x: torch.Tensor) -> ModelOutput:
        if not self._fitted:
            raise RuntimeError(
                "ClassicalMLBaseline.predict() called before fit(). "
                "Call model.fit(x_train, y_train) first."
            )
        if isinstance(x, dict):
            x_ref = x[self.contract.modalities[0]]
        else:
            x_ref = x
        B, T, C, H, W = x_ref.shape
        features = self._flatten_features(x)

        if self.contract.target_type == "binary":
            probs = self._estimator.predict_proba(features)[:, 1]  # P(class=1)
        else:
            probs = self._estimator.predict(features)

        prediction = torch.from_numpy(probs.astype(np.float32)).reshape(B, H, W)
        prediction = prediction.unsqueeze(1).unsqueeze(1)  # [B,1,1,H,W]

        return ModelOutput(
            prediction=prediction,
            model_name=self.model_name,
            model_version=self.model_version,
        )

    # ------------------------------------------------------------------
    # Serialization — separate from the torch checkpoint format since this
    # model has no state_dict. Mirrors save_checkpoint/load_checkpoint's
    # "self-describing" property: the saved file carries the DataContract
    # needed to reconstruct the wrapper.
    # ------------------------------------------------------------------

    def save(self, path: str) -> str:
        if not self._fitted:
            raise RuntimeError("Cannot save an unfitted ClassicalMLBaseline.")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        joblib.dump({
            "estimator": self._estimator,
            "contract": self.contract,
            "model_name": self.model_name,
            "model_version": self.model_version,
        }, path)
        return path

    @classmethod
    def load(cls, path: str) -> "ClassicalMLBaseline":
        payload = joblib.load(path)
        obj = cls(payload["contract"])
        obj._estimator = payload["estimator"]
        obj._fitted = True
        return obj
