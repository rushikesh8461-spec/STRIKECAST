#!/usr/bin/env python
"""Fail-closed canonical real-data training entry point.

The current real paired dataset contract is not yet backed by an approved
ERA5/LIS pairing builder. This command validates readiness and exits before
fit when the real dataset is absent or not accepted; it never falls back to
synthetic/demo data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "ml/research/strikecast")]
from src.ingestion.real_dataset import DatasetContractError, load_real_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/processed/real")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/training/real_data.yaml")
    args = parser.parse_args()
    if not args.config.is_file():
        print(json.dumps({"training_status": "ENVIRONMENT_FAILURE", "reason": "training_config_missing"}))
        return 3
    try:
        dataset = load_real_dataset(args.dataset)
    except DatasetContractError as exc:
        print(json.dumps({"training_status": "BLOCKED_BEFORE_FIT", "reason": str(exc)}))
        return 2
    print(json.dumps({"training_status": "BLOCKED_BEFORE_FIT", "dataset_version": dataset.manifest.get("dataset_version"),
                      "reason": "Canonical ERA5/LIS raw pairing and real-model training adapter are not implemented; no model was fit."}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
