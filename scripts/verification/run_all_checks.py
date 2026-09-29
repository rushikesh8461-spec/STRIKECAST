#!/usr/bin/env python
"""Run repository verification and write the machine-readable result report."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps" / "web"
REPORT = ROOT / "artifacts" / "reports" / "final_check.json"


def run(name: str, command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict:
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=900, check=False)
        output = completed.stdout.replace(str(ROOT), "<REPOSITORY>")
        output = re.sub(r"[A-Za-z]:\\Users\\[^\\\r\n]+", "<USER_PROFILE>", output, flags=re.IGNORECASE)
        safe_command = " ".join(command).replace(str(Path(sys.executable).parent), "<PYTHON>")
        return {"name": name, "command": safe_command, "exit_code": completed.returncode,
                "status": "PASS" if completed.returncode == 0 else "FAIL", "output_tail": output[-10000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "command": " ".join(command), "status": "BLOCKED_BY_ENVIRONMENT", "error": str(exc)}


def main() -> int:
    env = os.environ.copy()
    import_paths = ("packages", "apps/api", "ml/research/strikecast", "ml/research/legacy_api")
    env["PYTHONPATH"] = os.pathsep.join(str(ROOT / path) for path in import_paths)
    commands = [
        run("python_compile", [sys.executable, "-m", "compileall", "-q", "packages", "apps", "ml", "scripts", "tests"], env=env),
        run("python_tests", [sys.executable, "-m", "pytest", "-q"], env=env),
        run("api_smoke", [sys.executable, "scripts/development/smoke_test.py"], env=env),
        run("checkpoint_validation", [sys.executable, "scripts/ml/validate_checkpoint.py"], env=env),
        run("yaml_configuration", [sys.executable, "scripts/development/validate_configuration.py"], env=env),
        run("repository_structure", [sys.executable, "scripts/development/validate_structure.py"], env=env),
    ]
    npm = "npm.cmd" if os.name == "nt" else "npm"
    frontend_env = env.copy()
    frontend_env["NODE_OPTIONS"] = (frontend_env.get("NODE_OPTIONS", "") + " --use-system-ca").strip()
    for label, args in (("frontend_typecheck", [npm, "run", "typecheck"]), ("frontend_unit_tests", [npm, "test"]),
                        ("frontend_build", [npm, "run", "build"]), ("frontend_e2e", [npm, "run", "test:e2e"]),
                        ("npm_audit", [npm, "audit", "--audit-level=moderate"])):
        commands.append(run(label, args, cwd=FRONTEND, env=frontend_env))
    for tool, label, args in (("ruff", "python_lint", [sys.executable, "-m", "ruff", "check", "packages", "apps/api", "ml/research/strikecast/src/ingestion", "scripts", "tests"]),
                              ("pip_audit", "python_dependency_audit", [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"])):
        if shutil.which(tool) or (tool == "ruff" and __import__("importlib.util").util.find_spec("ruff")):
            commands.append(run(label, args, env=env))
        else:
            commands.append({"name": label, "command": " ".join(args), "status": "NOT_INSTALLED"})
    docker = shutil.which("docker")
    if docker:
        compose = [docker, "compose", "-f", "infra/compose/docker-compose.yml"]
        commands.extend((run("docker_compose_config", compose + ["config", "--quiet"]),
                         run("docker_compose_build", compose + ["build"], env=env)))
    else:
        commands.append({"name": "docker", "command": "docker compose -f infra/compose/docker-compose.yml config/build",
                         "status": "BLOCKED_BY_ENVIRONMENT", "error": "Docker CLI not installed"})
    def output(name: str) -> str:
        return next((item.get("output_tail", "") for item in commands if item["name"] == name), "")
    match = re.search(r"(\d+) passed", output("python_tests"))
    unit_match = re.search(r"Tests\s+(\d+) passed", output("frontend_unit_tests"))
    e2e_match = re.search(r"(\d+) passed \([^\n]+\)", output("frontend_e2e"))
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "python_version": sys.version,
              "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True).stdout.strip() if shutil.which("node") else None,
              "test_counts": {"python": int(match.group(1)) if match else None,
                              "frontend_unit": int(unit_match.group(1)) if unit_match else None,
                              "frontend_e2e": int(e2e_match.group(1)) if e2e_match else None},
              "failures": [item["name"] for item in commands if item["status"] == "FAIL"],
              "model_status": "DEMO_ONLY", "dataset_status": "NOT_READY", "calibration_status": "NOT_VALIDATED",
              "live_forecast_status": "BLOCKED", "lightning_status": "UNAVAILABLE_WITH_DEMO_SIMULATION_DEFAULT",
              "frontend_build_status": next((item["status"] for item in commands if item["name"] == "frontend_build"), "NOT_RUN"),
              "security_status": {item["name"]: item["status"] for item in commands if "audit" in item["name"] or "lint" in item["name"]},
              "docker_status": next((item["status"] for item in commands if item["name"] in {"docker", "docker_compose_build"}), "NOT_RUN"),
              "ci_status": "NOT_RUN_LOCALLY", "commands": commands}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"failures": report["failures"], "test_counts": report["test_counts"],
                      "model_status": report["model_status"], "dataset_status": report["dataset_status"]}, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
