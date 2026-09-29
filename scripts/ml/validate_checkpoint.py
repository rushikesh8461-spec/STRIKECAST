#!/usr/bin/env python
"""Validate the pinned demo checkpoint with the production-safe loader."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO_CHECKPOINT = ROOT / "artifacts" / "models" / "demo" / "strikecast_convlstm_demo.pt"
DEMO_METADATA = DEMO_CHECKPOINT.with_suffix(".json")
sys.path.insert(0, str(ROOT / "packages"))
from strikecast_core.models.inference import TrainedConvLSTM  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEMO_CHECKPOINT)
    args = parser.parse_args()
    result = {"model_status": "REJECTED", "path": str(args.checkpoint.name)}
    try:
        if args.checkpoint.resolve() != DEMO_CHECKPOINT.resolve():
            raise ValueError("Only the reviewed demo checkpoint is allowed by this validator")
        predictor = TrainedConvLSTM()
        metadata = json.loads(DEMO_METADATA.read_text(encoding="utf-8"))
        actual_sha256 = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        if metadata.get("sha256") != actual_sha256 or metadata.get("status") != "DEMO_ONLY":
            raise ValueError("Model manifest checksum or status does not match the checkpoint")
        result.update({"model_status": "DEMO_ONLY", "model_name": predictor.name,
                       "model_version": predictor.version,
                       "sha256": actual_sha256, "feature_version": metadata.get("feature_version"),
                       "dataset_version": metadata.get("dataset_version"),
                       "architecture": "ConvLSTMClassifier", "safe_load": True})
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, indent=2))
    return 0 if result["model_status"] == "DEMO_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
