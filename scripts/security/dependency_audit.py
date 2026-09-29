#!/usr/bin/env python
"""Run ecosystem vulnerability audits without weakening TLS verification."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts/reports/DEPENDENCY_AUDIT.json"


def run(label: str, args: list[str], cwd: Path = ROOT) -> dict:
    try:
        if label == "npm" and os.name == "nt":
            # npm is commonly exposed as a .cmd shim on Windows; execute the
            # fixed audit command through cmd.exe while retaining captured output.
            command = ["cmd.exe", "/d", "/s", "/c", "npm.cmd audit --audit-level=moderate --json"]
        else:
            command = args
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ecosystem": label, "status": "UNAVAILABLE", "reason": type(exc).__name__}
    output = (proc.stdout + "\n" + proc.stderr).lower()
    if proc.returncode == 0:
        if "skip reason" in output and "could not deduce package version" in output:
            return {"ecosystem": label, "status": "UNAVAILABLE", "reason": "editable_or_unpinned_requirement_skipped"}
        return {"ecosystem": label, "status": "PASS"}
    if any(term in output for term in ("certificate verify failed", "unable to verify the first certificate", "unable to get local issuer certificate", "ssl", "tls", "connectionerror", "timed out", "temporary failure", "network is unreachable")):
        return {"ecosystem": label, "status": "UNAVAILABLE", "reason": "registry_or_network_unavailable"}
    if any(term in output for term in ("vulnerabilit", "advisory", "found 0 vulnerabilities") if term != "found 0 vulnerabilities"):
        return {"ecosystem": label, "status": "VULNERABLE", "return_code": proc.returncode}
    return {"ecosystem": label, "status": "UNAVAILABLE", "reason": f"audit_tool_or_manifest_error_{proc.returncode}"}


def main() -> int:
    results = [run("python", [sys.executable, "-m", "pip_audit", "--disable-pip", "--no-deps", "-r", "requirements.txt"])]
    if (ROOT / "apps/web/package-lock.json").is_file():
        npm = os.environ.get("STRIKECAST_NPM", "npm")
        results.append(run("npm", [npm, "audit", "--audit-level=moderate", "--json"], ROOT / "apps/web"))
    status = "VULNERABLE" if any(x["status"] == "VULNERABLE" for x in results) else (
        "UNAVAILABLE" if any(x["status"] == "UNAVAILABLE" for x in results) else "PASS")
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": status, "audits": results,
              "tls_verification_disabled": False}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Dependency audit", "", f"Status: **{status}**", "",
             "TLS verification was not disabled.", "", "| Ecosystem | Status | Reason |", "|---|---|---|"]
    lines.extend(f"| {item['ecosystem']} | {item['status']} | {item.get('reason', 'none')} |" for item in results)
    (REPORT.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return {"PASS": 0, "VULNERABLE": 1, "UNAVAILABLE": 2}[status]


if __name__ == "__main__":
    raise SystemExit(main())
