#!/usr/bin/env python
"""Validate frozen monorepo boundaries, artifact status, and repository hygiene."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    ".github", "apps/api", "apps/web", "packages/strikecast_core", "ml", "data",
    "artifacts", "configs", "scripts", "tests", "docs", "infra",
    "apps/api/strikecast_api/main.py", "apps/web/package.json",
    "packages/strikecast_core/__init__.py", "packages/strikecast_core/schemas/api.py",
    "packages/strikecast_core/data/atmospheric.py", "packages/strikecast_core/features/point.py",
    "packages/strikecast_core/models/inference.py", "packages/strikecast_core/evaluation/metrics.py",
    "packages/strikecast_core/risk/engine.py", "packages/strikecast_core/security/checkpoints.py",
    "ml/training", "ml/experiments", "ml/research", "data/demo", "data/manifests", "data/raw",
    "data/interim", "data/processed", "artifacts/models/demo/strikecast_convlstm_demo.pt",
    "artifacts/models/demo/strikecast_convlstm_demo.json", "artifacts/models/candidate/README.md",
    "artifacts/models/production/README.md", "configs", "scripts", "tests", "docs", "infra",
)
OLD_MODULES = tuple(f"m{index}-{name}" for index, name in enumerate(
    ("data", "features", "model", "risk", "backend", "frontend"), start=1
))
OLD_TOP_LEVEL = (*OLD_MODULES, "strikecast")
GENERATED_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "dist", "build", "test-results", "playwright-report"}
SKIP_DIRS = {".git", ".venv", *GENERATED_DIRS}
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".ts", ".tsx", ".js", ".css", ".html", ".sh", ".ps1", ".bat", ".txt", ".conf"}
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+/)", re.IGNORECASE)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
INLINE_SECRET = re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\b\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-=]{24,})")
OLD_REF = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(name) for name in OLD_MODULES) + r")(?:[/\\`.]|\b)")


def walk_files():
    for current, directories, filenames in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in SKIP_DIRS]
        for filename in filenames:
            yield Path(current) / filename


def main() -> int:
    errors: list[str] = []
    for current, directories, _ in os.walk(ROOT):
        for name in directories:
            if name in GENERATED_DIRS:
                errors.append(f"generated directory remains: {(Path(current) / name).relative_to(ROOT).as_posix()}")
        directories[:] = [name for name in directories if name not in {".git", ".venv", *GENERATED_DIRS}]
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.exists():
            errors.append(f"missing required path: {relative}")
    for name in OLD_TOP_LEVEL:
        if (ROOT / name).exists():
            errors.append(f"obsolete top-level directory remains: {name}")

    # Outside the explicitly research-only compatibility area, only one API and
    # one runtime risk/model implementation may be defined.
    api_apps = [p for p in ROOT.rglob("*.py") if p.name != "validate_structure.py" and "node_modules" not in p.parts
                and "legacy_api" not in p.parts and "research" not in p.parts
                and "FastAPI(" in p.read_text(encoding="utf-8", errors="ignore")]
    if api_apps != [ROOT / "apps/api/strikecast_api/main.py"]:
        errors.append("served FastAPI boundary is not uniquely apps/api/strikecast_api/main.py")
    risk_engines = [p for p in ROOT.rglob("*.py") if p.name != "validate_structure.py"
                    and "legacy_api" not in p.parts and "research" not in p.parts
                    and "def assess_risk(" in p.read_text(encoding="utf-8", errors="ignore")]
    if risk_engines != [ROOT / "packages/strikecast_core/risk/engine.py"]:
        errors.append("canonical risk assessment is not unique in strikecast_core")
    runtime_models = [p for p in (ROOT / "packages/strikecast_core").rglob("*.py")
                      if "class ConvLSTMClassifier" in p.read_text(encoding="utf-8", errors="ignore")]
    if runtime_models != [ROOT / "packages/strikecast_core/models/runtime_convlstm.py"]:
        errors.append("runtime ConvLSTM definition is not unique in strikecast_core")
    checkpoint_loaders = [p for p in (ROOT / "packages/strikecast_core").rglob("*.py")
                          if "def load_verified_checkpoint(" in p.read_text(encoding="utf-8", errors="ignore")]
    if checkpoint_loaders != [ROOT / "packages/strikecast_core/security/checkpoints.py"]:
        errors.append("canonical verified checkpoint loader is not unique in strikecast_core")
    schema_sources = [p for base in (ROOT / "packages/strikecast_core", ROOT / "apps/api")
                      for p in base.rglob("*.py")
                      if "class PredictionRequest(" in p.read_text(encoding="utf-8", errors="ignore")]
    if schema_sources != [ROOT / "packages/strikecast_core/schemas/api.py"]:
        errors.append("canonical API schema source is not unique in strikecast_core")

    production = ROOT / "artifacts/models/production"
    if production.exists() and any(p.suffix.lower() in {".pt", ".pth", ".onnx", ".safetensors"} for p in production.rglob("*")):
        errors.append("production model slot contains an unreviewed checkpoint")
    artifact = ROOT / "artifacts/models/demo/strikecast_convlstm_demo.pt"
    metadata_path = artifact.with_suffix(".json")
    if artifact.is_file() and metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if metadata.get("sha256") != digest or metadata.get("status") != "DEMO_ONLY":
            errors.append("demo model manifest checksum/status mismatch")
        if metadata.get("dataset") != "synthetic/demo" or metadata.get("dataset_version") != "not independently released":
            errors.append("demo model dataset provenance is not explicit")
        if not metadata.get("model") or not metadata.get("version") or not metadata.get("feature_version") or not metadata.get("dataset_version"):
            errors.append("demo model manifest is missing traceability metadata")

    for path in walk_files():
        if path.suffix.lower() == ".pyc":
            errors.append(f"generated bytecode remains: {path.relative_to(ROOT).as_posix()}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.name == ".env":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if LOCAL_PATH.search(content):
            errors.append(f"machine-specific path present: {rel}")
        if PRIVATE_KEY.search(content) or INLINE_SECRET.search(content):
            errors.append(f"possible committed secret present: {rel}")
        historical = {"docs/architecture/MIGRATION_MAP.md", "docs/archive/INTEGRATION_AUDIT.md",
                      "docs/reports/FINAL_STRUCTURE_REPORT.md", "scripts/development/validate_structure.py"}
        if rel not in historical and OLD_REF.search(content):
            errors.append(f"old M1-M6 path reference outside historical docs: {rel}")

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"Structure checks passed ({len(REQUIRED)} required paths; unique served API/model/risk; no production checkpoint; demo manifest verified; no old roots, generated caches, machine paths, or obvious secrets).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
