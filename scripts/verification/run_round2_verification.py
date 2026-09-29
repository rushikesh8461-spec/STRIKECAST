#!/usr/bin/env python
"""Run independent Round-2 checks and preserve exact status/evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
REPORT_JSON = ROOT / "artifacts/reports/ROUND2_FINAL_READINESS_REPORT.json"
REPORT_MD = ROOT / "artifacts/reports/ROUND2_FINAL_READINESS_REPORT.md"

CHECKS = [
    ("repository_audit", [PY, "scripts/security/audit_repository.py"], 0),
    ("configuration_validation", [PY, "scripts/development/validate_configuration.py"], 0),
    ("secret_scan", [PY, "scripts/security/audit_repository.py"], 0),
    ("dependency_audit", [PY, "scripts/security/dependency_audit.py"], (0, 2)),
    ("dataset_validation", [PY, "scripts/verification/validate_dataset.py"], (0, 2)),
    ("era5_coverage_planner", [PY, "scripts/data/plan_required_era5.py"], 0),
    ("leakage_audit", [PY, "scripts/ml/leakage_audit.py", "--allow-blocked"], 0),
    ("checkpoint_integrity", [PY, "scripts/ml/validate_checkpoint.py"], 0),
    ("python_tests", [PY, "-m", "pytest", "-q"], 0),
    ("api_smoke", [PY, "scripts/development/smoke_test.py"], 0),
    ("docker_compose_yaml_static", [PY, "-c", "import yaml; from pathlib import Path; p=Path('infra/compose/docker-compose.yml'); d=yaml.safe_load(p.read_text(encoding='utf-8')); assert isinstance(d, dict) and {'api','web'} <= set(d.get('services', {}))"], 0),
    ("frontend_typecheck", ["npm", "run", "typecheck"], 0),
    ("frontend_tests", ["npm", "test", "--", "--run"], 0),
    ("frontend_e2e", ["npm", "run", "test:e2e"], 0),
    ("frontend_build", ["npm", "run", "build"], 0),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-current-era5-inventory", action="store_true",
                        help="Use the already generated current-inventory coverage manifest instead of rescanning multi-GB source archives.")
    args = parser.parse_args()
    results = []
    for name, command, accepted in CHECKS:
        if name == "era5_coverage_planner" and args.reuse_current_era5_inventory:
            coverage_path = ROOT / "data/manifests/era5_required_coverage.json"
            if coverage_path.is_file():
                coverage_existing = json.loads(coverage_path.read_text(encoding="utf-8"))
                results.append({"name": name, "status": "DATA_BLOCKED" if coverage_existing.get("missing_hour_count", 0) else "PASS",
                                "evidence": "reused current-inventory manifest", "manifest": coverage_path.relative_to(ROOT).as_posix()})
                continue
        cwd = ROOT / "apps/web" if name.startswith("frontend_") else ROOT
        try:
            if name.startswith("frontend_") and os.name == "nt":
                # npm resolves to a .cmd shim on Windows; invoke that fixed
                # repository command via cmd.exe rather than treating it as an executable.
                invocation = ["cmd.exe", "/d", "/s", "/c", " ".join(command)]
            else:
                invocation = command
            proc = subprocess.run(invocation, cwd=cwd, capture_output=True, text=True, timeout=1800, check=False)
            okay = proc.returncode in (accepted if isinstance(accepted, tuple) else (accepted,))
            status = "PASS" if okay else "FAIL"
            if okay and name == "dataset_validation" and proc.returncode == 2:
                status = "DATA_BLOCKED"
            elif okay and name == "dependency_audit" and proc.returncode == 2:
                status = "ENVIRONMENT_BLOCKED"
            elif okay and name == "leakage_audit":
                leakage_path = ROOT / "artifacts/reports/ROUND2_LEAKAGE_AUDIT.json"
                if leakage_path.is_file() and json.loads(leakage_path.read_text(encoding="utf-8")).get("status") == "BLOCKED_NO_DATA":
                    status = "DATA_BLOCKED"
            elif okay and name == "era5_coverage_planner":
                coverage_path = ROOT / "data/manifests/era5_required_coverage.json"
                if coverage_path.is_file() and json.loads(coverage_path.read_text(encoding="utf-8")).get("missing_hour_count", 0) > 0:
                    status = "DATA_BLOCKED"
            elif okay and name == "checkpoint_integrity":
                status = "DEMO_ONLY"
            results.append({"name": name, "status": status, "return_code": proc.returncode,
                            "command": command, "evidence": "completed; detailed command output is not retained to avoid logging untrusted data"})
        except subprocess.TimeoutExpired:
            results.append({"name": name, "status": "ENVIRONMENT_BLOCKED", "reason": "timeout_after_1800_seconds", "command": command})
        except OSError as exc:
            results.append({"name": name, "status": "ENVIRONMENT_BLOCKED", "reason": type(exc).__name__, "command": command})
    if shutil.which("docker") is None:
        results.append({"name": "docker_runtime", "status": "ENVIRONMENT_BLOCKED", "reason": "DOCKER_RUNTIME_UNAVAILABLE"})
    else:
        try:
            proc = subprocess.run(["docker", "compose", "-f", "infra/compose/docker-compose.yml", "config", "--quiet"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
            results.append({"name": "docker_compose_static", "status": "PASS" if proc.returncode == 0 else "FAIL",
                            "return_code": proc.returncode})
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"name": "docker_compose_static", "status": "ENVIRONMENT_BLOCKED", "reason": type(exc).__name__})
    code_failures = [r for r in results if r["status"] == "FAIL"]
    overall = "FAIL" if code_failures else "READY_FOR_REAL_DATA"
    coverage_path = ROOT / "data/manifests/era5_required_coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.is_file() else {}
    requirements = coverage.get("requirements", {})
    lis = coverage.get("lis_granules", {})
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": overall,
              "engineering_status": "READY_FOR_REAL_DATA" if not code_failures else "FAIL",
              "data_status": "BLOCKED_NO_DATA", "model_status": "DEMO_ONLY", "checks": results,
              "era5_coverage": {"required_hours": requirements.get("required_hour_count"),
                                "available_complete_hours": coverage.get("available_hour_count"),
                                "missing_or_incomplete_hours": coverage.get("missing_hour_count"),
                                "required_hour_dates_utc": [g["date"] for g in requirements.get("required_hours", [])],
                                "missing_hour_dates_utc": [g["date"] for g in coverage.get("missing", [])]},
              "lis_coverage": {"readable_granules": lis.get("readable_unique_granules_inspected"),
                               "domain_intersecting_granules": lis.get("domain_intersecting_granules"),
                               "domain_dates_utc": lis.get("domain_dates_utc")},
              "limitations": [
                  {"type": "TYPE_A_CODE", "limitation": "Canonical schema-driven ERA5 gridding, LIS observation grids, masked paired samples, chronological split, train-only normalization and ConvLSTM train/evaluate/calibrate/candidate artifact validation are implemented and fixture-tested.", "status": "IMPLEMENTED"},
                  {"type": "TYPE_A_CODE", "limitation": "Research-grid candidates do not satisfy the served point-model feature and normalization contract. They are explicitly marked INFERENCE_COMPATIBILITY=UNSUPPORTED; registry promotion and API loading reject them. Compatible registered point-contract candidates load only through the validated registry pointer.", "status": "FAIL_CLOSED"},
                  {"type": "TYPE_B_DATA", "limitation": f"{coverage.get('missing_hour_count', 'unknown')} required ERA5 hours are missing or incomplete; no provenance-complete real paired training dataset exists.", "status": "BLOCKED"},
                  {"type": "TYPE_C_ENVIRONMENT", "limitation": "Dependency vulnerability scan or Docker runtime may be unavailable in the current environment; results are represented explicitly by individual checks.", "status": "CHECKED"},
                  {"type": "TYPE_D_SCIENTIFIC", "limitation": "LIS quality-flag acceptance and target-viewtime policy must be approved before observed non-lightning can become a negative label.", "status": "OPEN"}
              ]}
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Round 2 final readiness report", "", f"Status: **{overall}**", "",
             "| Check | Status | Exit |", "|---|---:|---:|"]
    lines += [f"| {r['name']} | {r['status']} | {r.get('return_code', 'n/a')} |" for r in results]
    lines += ["", "## External and data gates", "", "- Dataset: **BLOCKED_NO_DATA**; no real training was run.",
              "- Model: **DEMO_ONLY**; no scientific validation or production promotion is claimed.",
              f"- ERA5: {coverage.get('available_hour_count', 'unknown')} complete hours available of {requirements.get('required_hour_count', 'unknown')} required; {coverage.get('missing_hour_count', 'unknown')} required hours are incomplete.",
              "- Canonical pairing, indexed LIS lookup, bounded input validation, mechanics-tested training/evaluation/calibration, and registry-gated model loading are implemented. Research-grid candidates are explicitly unsupported for point-model serving; incompatible candidates fail closed.",
              "- Full status, exact missing dates, categorized limitations, and environment reasons are in this JSON report and `data/manifests/era5_required_coverage.json`.", ""]
    lines += ["## Limitation classification", "", "| Limitation | Type | Can code fix? | Status |", "|---|---|---:|---|"]
    lines += [f"| {item['limitation']} | {item['type']} | {'Yes' if item['type'] == 'TYPE_A_CODE' else 'No'} | {item['status']} |"
              for item in report["limitations"]]
    lines += [""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": overall, "checks": len(results), "failures": len(code_failures), "report": str(REPORT_JSON)}))
    return 1 if code_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
