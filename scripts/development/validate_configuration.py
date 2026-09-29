#!/usr/bin/env python
"""Parse repository YAML configuration/workflow files for syntax errors."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
FILES = [*ROOT.joinpath("configs").rglob("*.yaml"), *ROOT.joinpath("ml/experiments/configs").rglob("*.yaml"),
         *ROOT.joinpath(".github/workflows").glob("*.yml")]
JSON_FILES = list(ROOT.joinpath("configs").rglob("*.json"))


def main() -> int:
    failed = []
    parsed = {}
    for path in FILES:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict): raise ValueError("expected a YAML mapping")
            parsed[path.relative_to(ROOT).as_posix()] = value
        except Exception as exc:
            failed.append((path.relative_to(ROOT).as_posix(), str(exc)))
    for path in JSON_FILES:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict): raise ValueError("expected a JSON object")
            parsed[path.relative_to(ROOT).as_posix()] = value
        except Exception as exc:
            failed.append((path.relative_to(ROOT).as_posix(), str(exc)))
    data_config = parsed.get("configs/data.yaml", {})
    contract = data_config.get("real_dataset", {}).get("acceptance_contract")
    if not isinstance(contract, str) or not (ROOT / contract).is_file():
        failed.append(("configs/data.yaml", f"real_dataset.acceptance_contract does not resolve: {contract!r}"))
    if failed:
        for path, error in failed: print(f"FAIL {path}: {error}")
        return 1
    print(f"Parsed {len(FILES)} YAML configuration/workflow files and {len(JSON_FILES)} JSON configuration files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
