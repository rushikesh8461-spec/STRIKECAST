#!/usr/bin/env python
"""Generate repository architecture inventory and a high-confidence secret scan.

Secret match values are never written to stdout or reports. This scanner is
heuristic and does not replace a managed secret scanner or human review.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SKIP = {"node_modules", ".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build", "test-results"}
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".ts", ".tsx", ".js", ".css", ".html", ".sh", ".ps1", ".bat", ".txt", ".conf", ".env"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "jwt_like": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "credential_assignment": re.compile(r"(?i)\b(?:password|client_secret|api_key|access_token)\b\s*[:=]\s*['\"]([^'\"]{16,})['\"]"),
}
PLACEHOLDERS = ("example", "placeholder", "changeme", "your_", "<", "${", "not-a-secret", "dummy")


def files():
    for current, dirs, names in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in SKIP]
        for name in names:
            path = Path(current) / name
            if path.suffix.lower() in TEXT_SUFFIXES or name == ".env":
                try:
                    if path.stat().st_size <= 4 * 1024 * 1024:
                        yield path
                except OSError:
                    continue


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    file_list = list(files())
    findings = []
    for path in file_list:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for category, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                value = match.group(1) if category == "credential_assignment" else match.group(0)
                if category == "credential_assignment" and any(word in value.lower() for word in PLACEHOLDERS):
                    continue
                findings.append({"category": category, "path": path.relative_to(ROOT).as_posix()})
                break
    top = ["apps/api", "apps/web", "packages/strikecast_core", "ml", "data", "artifacts", "configs", "scripts", "tests", "docs", "infra", ".github"]
    counts = {}
    for name in top:
        folder = ROOT / name
        counts[name] = sum(1 for p in folder.rglob("*") if p.is_file() and not any(part in SKIP for part in p.parts)) if folder.exists() else 0
    secret = {"generated_at_utc": now, "status": "FOUND" if findings else "NOT_FOUND_BY_CONFIGURED_HEURISTICS", "finding_count": len(findings), "findings": findings,
              "scope": "UTF-8 source/config/docs/tests/manifests/artifacts; generated node_modules, build output, caches, and binary/raw payloads excluded",
              "limitation": "Pattern-based scan can miss novel, encoded, split, or binary secrets and may flag non-secret test fixtures; use managed secret scanning and review findings."}
    report_dir = ROOT / "artifacts/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "SECRET_SCAN_REPORT.md").write_text(
        f"# Secret scan report\n\nStatus: **{secret['status']}**. High-confidence pattern findings: {len(findings)}.\n\n"
        f"Scope: {secret['scope']}.\n\n" +
        ("Potential findings (values intentionally withheld):\n\n" + "\n".join(f"- `{x['path']}` ({x['category']})" for x in findings) + "\n\n" if findings else "No configured high-confidence credential patterns matched scanned text files.\n\n") +
        f"Limitation: {secret['limitation']}\n", encoding="utf-8")
    (report_dir / "SECRET_SCAN_REPORT.json").write_text(json.dumps(secret, indent=2) + "\n", encoding="utf-8")

    observations = [
        {"id": "ARCH-001", "severity": "INFO", "finding": "One served FastAPI app is defined at apps/api/strikecast_api/main.py; core package owns API schemas and the runtime risk/model boundary.", "status": "PASS_BY_STATIC_INVENTORY"},
        {"id": "ARCH-002", "severity": "MEDIUM", "finding": "Research and training trees contain separate ConvLSTM/model and trainer implementations from the served core; they are retained for experiments and are not interchangeable.", "status": "DOCUMENTED_NOT_CONSOLIDATED"},
        {"id": "ARCH-003", "severity": "HIGH", "finding": "No canonical raw ERA5/LIS paired dataset builder exists. The guarded CLI is demo-only and strict prepared-data loader is not a provider adapter.", "status": "BLOCKED"},
        {"id": "ARCH-004", "severity": "MEDIUM", "finding": "API rate limiter is process-local memory and does not protect a multi-worker deployment consistently.", "status": "OPEN"},
        {"id": "ARCH-005", "severity": "HIGH", "finding": "Development launcher enables reload and binds 0.0.0.0; it must not be treated as production deployment.", "status": "OPEN"},
        {"id": "ARCH-006", "severity": "MEDIUM", "finding": "No Git metadata is present in this checkout; commit-based provenance and working-tree diff cannot be verified.", "status": "ENVIRONMENT_LIMITATION"},
        {"id": "ARCH-007", "severity": "MEDIUM", "finding": "ZIP inventory validates metadata/CRC without extraction; no canonical safe extraction utility is present. Any future extraction requires containment and expansion limits.", "status": "DOCUMENTED"},
        {"id": "ARCH-008", "severity": "MEDIUM", "finding": "Python requirements are not a complete hash-locked environment; web app has package-lock.json. Dependency audit required.", "status": "OPEN"},
        {"id": "ARCH-009", "severity": "MEDIUM", "finding": "The verified checkpoint loader currently approves only a hardcoded demo artifact digest and metadata; there is no generic signed candidate registry.", "status": "DEMO_ONLY"},
        {"id": "ARCH-010", "severity": "LOW", "finding": "No automated production model promotion is configured; candidate acceptance is BLOCKED and production model slot is empty.", "status": "SAFE_BLOCKED"},
        {"id": "ARCH-011", "severity": "MEDIUM", "finding": "API middleware logs rounded location buckets; retention/privacy requirements should determine whether this telemetry is necessary.", "status": "OPEN_REVIEW"},
        {"id": "ARCH-012", "severity": "MEDIUM", "finding": "Runtime API response schema validation is delegated to FastAPI response_model; failures are generic 500 but no dedicated response-contract test covers every endpoint.", "status": "OPEN_REVIEW"},
    ]
    audit = {"generated_at_utc": now, "repository_root": ".", "git_commit": None, "git_metadata_available": False,
             "file_counts_including_generated_excluded": counts, "text_files_scanned_for_secrets": len(file_list),
             "secret_scan_status": secret["status"], "canonical_architecture": {
                 "api": "apps/api/strikecast_api/main.py", "runtime_model": "packages/strikecast_core/models/runtime_convlstm.py",
                 "api_schema": "packages/strikecast_core/schemas/api.py", "prepared_dataset": "ml/research/strikecast/src/ingestion/real_dataset.py",
                 "target": "ml/research/strikecast/src/preprocessing/target.py", "feature_schema": "configs/data/feature_schema.yaml",
                 "training_cli": "scripts/ml/train.py (DEMO only)", "evaluation": "scripts/ml/evaluate.py (research utility)",
                 "registry": "artifacts/models/{demo,candidate,production}", "configuration": "configs/"},
             "observations": observations,
             "audit_scope": ["apps/api", "apps/web", "packages/strikecast_core", "ml", "data", "artifacts", "configs", "scripts", "tests", "docs", "infra", ".github"],
             "limitations": ["No Git repository metadata is available.", "Static source scanning does not establish absence of all vulnerabilities.", "Binary raw dataset payloads and node_modules are excluded from secret text scanning; binary credential scanning was not performed.", "Provider source claims, operational availability semantics, and deployment topology require owner verification."]}
    (report_dir / "ROUND2_ARCHITECTURE_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {x['id']} | {x['severity']} | {x['status']} | {x['finding']} |" for x in observations)
    (report_dir / "ROUND2_ARCHITECTURE_AUDIT.md").write_text(
        f"# Round 2 architecture and security audit\n\nGenerated {now}. Scope: {', '.join(top)}.\n\n"
        "Git metadata: **UNAVAILABLE** in this checkout; source commit and change diff could not be verified.\n\n"
        "## Canonical ownership\n\n| Capability | Canonical location | Status |\n|---|---|---|\n"
        "| Served API | `apps/api/strikecast_api/main.py` | one served FastAPI app |\n"
        "| Runtime model | `packages/strikecast_core/models/runtime_convlstm.py` + `models/inference.py` | demo checkpoint only |\n"
        "| API schema | `packages/strikecast_core/schemas/api.py` | shared request/response contracts |\n"
        "| Prepared dataset contract | `ml/research/strikecast/src/ingestion/real_dataset.py` + `docs/data/DATASET_CONTRACT.md` | strict loader; no raw pairing builder |\n"
        "| Target semantics | `ml/research/strikecast/src/preprocessing/target.py` | observed positive/negative/unknown mask |\n"
        "| Feature schema | `configs/data/feature_schema.yaml` | candidate schema; selected ERA5 semantics need validation |\n"
        "| Training | `scripts/ml/train.py` | DEMO-only guard |\n"
        "| Evaluation/calibration | `scripts/ml/evaluate.py`, `scripts/ml/calibrate.py` | utilities; no eligible real evaluation |\n"
        "| Registry | `artifacts/models/{demo,candidate,production}` | demo pinned; candidate blocked; production empty |\n\n"
        "## Findings\n\n| ID | Severity | Status | Finding |\n|---|---|---|---|\n" + rows + "\n\n"
        "## Security scan\n\n"
        f"Secret scanner status: **{secret['status']}** ({len(findings)} high-confidence matches). See `SECRET_SCAN_REPORT.md`; no matched values are emitted. Heuristics do not prove absence of secrets.\n\n"
        "Archive intake currently inspects ZIP metadata and CRC without extracting members; safe extraction is not implemented or needed by this workflow. Strict NPZ loading disables pickle and verifies path/checksum. API CORS disallows wildcard credentials; body limits and baseline headers exist. Distributed rate limiting, production launch configuration, signed artifacts and a full penetration review remain open.\n\n"
        "## Repository inventory\n\n" + "\n".join(f"- `{name}`: {count} files (generated directories excluded)" for name, count in counts.items()) + "\n\n"
        "Full observations and scope limitations are machine-readable in `ROUND2_ARCHITECTURE_AUDIT.json`.\n", encoding="utf-8")
    print(json.dumps({"architecture_findings": len(observations), "secret_scan_status": secret["status"], "secret_matches": len(findings), "text_files_scanned": len(file_list)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
