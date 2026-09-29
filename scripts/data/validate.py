#!/usr/bin/env python
"""Validate a provenance-bearing real dataset contract without training."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "ml/research/strikecast")]
from src.ingestion.real_dataset import DatasetContractError, load_real_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    try:
        dataset = load_real_dataset(args.dataset)
    except DatasetContractError as exc:
        print(json.dumps({"dataset_status": "NOT_READY", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"dataset_status": "CANDIDATE", "dataset_version": dataset.manifest["dataset_version"],
                      "splits": {name: int(len(dataset.arrays[f"X_{name}"])) for name in ("train", "validation", "test")},
                      "note": "Contract validation only; independent source review and model evaluation are still required."}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
