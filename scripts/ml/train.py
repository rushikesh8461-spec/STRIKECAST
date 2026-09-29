#!/usr/bin/env python
"""Guarded bridge to the existing M3 trainer; this CLI supports DEMO only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "ml/research/strikecast")]
from ml.training.strikecast_training.train import load_config, train_classical, train_nn_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["convlstm", "fusion_convlstm", "classical_ml"], default="convlstm")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--data", default="synthetic", choices=["synthetic", "m2-demo"])
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "models" / "demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["DEMO", "VALIDATION", "LIVE"], default="DEMO")
    args = parser.parse_args()
    if args.mode != "DEMO":
        parser.error("this trainer currently supports DEMO data only; no accepted real-data training adapter exists")
    config = load_config(str(args.config) if args.config else None)
    config.train.seed = args.seed
    config.train.data_source = "m2" if args.data == "m2-demo" else "synthetic"
    config.train.m2_demo = args.data == "m2-demo"
    config.train.checkpoint_dir = str(args.output.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    output = train_classical(config) if args.model == "classical_ml" else train_nn_model(config, args.model)
    print(f"DEMO_ONLY checkpoint written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
