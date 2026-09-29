#!/usr/bin/env python
"""Fail-closed leakage audit for a prepared StrikeCast real dataset.

The strict dataset loader validates feature availability cutoffs, chronology,
non-overlapping whole windows, duplicate samples, and train-only normalization
metadata. This command reports BLOCKED when no eligible manifest exists; it
never creates or repairs samples.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/research/strikecast"))
from src.ingestion.real_dataset import DatasetContractError, load_real_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="Prepared real dataset directory containing manifest.json")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/reports/ROUND2_LEAKAGE_AUDIT.json")
    parser.add_argument("--allow-blocked", action="store_true", help="CI mode: accept no-data BLOCKED status, while still failing detected contract errors")
    args = parser.parse_args()
    candidates = [args.dataset.resolve()] if args.dataset else sorted(
        path.parent for path in (ROOT / "data/processed").rglob("manifest.json")
        if not {"demo", "research"}.intersection(part.lower() for part in path.parts)
    )
    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_NO_DATA" if not candidates else "FAIL",
        "dataset_count": len(candidates),
        "checks": {
            "feature_availability_before_issue_time": "NOT_RUN_NO_DATASET",
            "future_target_excluded_from_features": "NOT_RUN_NO_DATASET",
            "normalization_fit_split_train_only": "NOT_RUN_NO_DATASET",
            "whole_windows_do_not_overlap_splits": "NOT_RUN_NO_DATASET",
            "calibration_and_selection_validation_only": "NOT_RUN_NO_DATASET",
            "duplicate_samples_across_splits": "NOT_RUN_NO_DATASET",
            "source_timestamp_cutoff": "NOT_RUN_NO_DATASET",
            "calibration_samples_excluded_from_test": "NOT_RUN_NO_DATASET",
        },
        "datasets": [],
        "limitations": [
            "A valid result proves contract invariants in the prepared arrays and manifest; it does not independently prove provider timestamps or source-record uniqueness.",
            "Raw ERA5/LIS pairing and source-level deduplication are not implemented as a canonical paired-data builder.",
        ],
    }
    for dataset in candidates:
        try:
            load_real_dataset(dataset)
            report["datasets"].append({"dataset": dataset.name, "status": "PASS_CONTRACT_LEAKAGE_GATES"})
        except (DatasetContractError, OSError, ValueError) as exc:
            report["datasets"].append({"dataset": dataset.name, "status": "FAIL", "reason": str(exc)})
            report["status"] = "FAIL"
    if candidates and report["status"] != "FAIL":
        report["status"] = "PASS_CONTRACT_LEAKAGE_GATES"
        report["checks"] = {key: "PASS" for key in report["checks"]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = [
        "# Round 2 leakage audit", "", f"Status: **{report['status']}**", "",
        f"Eligible datasets inspected: {len(candidates)}.", "",
        "| Leakage control | Result |", "|---|---|",
        *[f"| {key.replace('_', ' ')} | {value} |" for key, value in report["checks"].items()], "",
        "## Dataset results", "",
        *(f"- `{row['dataset']}`: {row['status']}" + (f" — {row['reason']}" if "reason" in row else "") for row in report["datasets"]),
        *( ["- No eligible real dataset manifest was found; checks were not run."] if not candidates else [] ), "",
        "This gate does not build data. A failure returns a nonzero exit code; no leakage finding is waived.", "",
        "## Limitations", "", *[f"- {item}" for item in report["limitations"]], "",
    ]
    (ROOT / "artifacts/reports/ROUND2_LEAKAGE_AUDIT.md").write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps({"status": report["status"], "datasets": len(candidates), "report": str(args.report)}))
    return 1 if report["status"] == "FAIL" else (0 if candidates or args.allow_blocked else 2)


if __name__ == "__main__":
    raise SystemExit(main())
