#!/usr/bin/env python
"""Fail-closed validation for a prepared, provenance-bearing real dataset.

Exit codes: 0 valid, 1 invalid, 2 insufficient/no data, 3 environment failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "ml/research/strikecast")]
from src.ingestion.real_dataset import DatasetContractError, load_real_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="Prepared real dataset directory")
    args = parser.parse_args()
    candidates = [args.dataset] if args.dataset else sorted(
        p.parent for p in (ROOT / "data/processed").rglob("manifest.json")
        if not {"demo", "research"}.intersection(part.lower() for part in p.parts)
    )
    if not candidates:
        print(json.dumps({"dataset_status": "BLOCKED_NO_DATA", "error": "No prepared real dataset manifest found."}))
        return 2
    try:
        datasets = [load_real_dataset(path) for path in candidates]
    except (DatasetContractError, ValueError) as exc:
        print(json.dumps({"dataset_status": "INVALID", "error": str(exc)}, indent=2))
        return 1
    except OSError as exc:
        print(json.dumps({"dataset_status": "ENVIRONMENT_FAILURE", "error": str(exc)}, indent=2))
        return 3
    results = [{"dataset_version": data.manifest["dataset_version"],
                "splits": {name: len(data.arrays[f"X_{name}"]) for name in ("train", "validation", "test")}}
               for data in datasets]
    print(json.dumps({"dataset_status": "VALID", "datasets": results,
                      "note": "Contract validation is not scientific model validation."}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
