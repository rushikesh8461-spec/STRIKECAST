# Round 2 architecture and security audit

Generated 2026-09-28T21:43:24.470554+00:00. Scope: apps/api, apps/web, packages/strikecast_core, ml, data, artifacts, configs, scripts, tests, docs, infra, .github.

Git metadata: **UNAVAILABLE** in this checkout; source commit and change diff could not be verified.

## Canonical ownership

| Capability | Canonical location | Status |
|---|---|---|
| Served API | `apps/api/strikecast_api/main.py` | one served FastAPI app |
| Runtime model | `packages/strikecast_core/models/runtime_convlstm.py` + `models/inference.py` | demo checkpoint only |
| API schema | `packages/strikecast_core/schemas/api.py` | shared request/response contracts |
| Prepared dataset contract | `ml/research/strikecast/src/ingestion/real_dataset.py` + `docs/data/DATASET_CONTRACT.md` | strict loader; no raw pairing builder |
| Target semantics | `ml/research/strikecast/src/preprocessing/target.py` | observed positive/negative/unknown mask |
| Feature schema | `configs/data/feature_schema.yaml` | candidate schema; selected ERA5 semantics need validation |
| Training | `scripts/ml/train.py` | DEMO-only guard |
| Evaluation/calibration | `scripts/ml/evaluate.py`, `scripts/ml/calibrate.py` | utilities; no eligible real evaluation |
| Registry | `artifacts/models/{demo,candidate,production}` | demo pinned; candidate blocked; production empty |

## Findings

| ID | Severity | Status | Finding |
|---|---|---|---|
| ARCH-001 | INFO | PASS_BY_STATIC_INVENTORY | One served FastAPI app is defined at apps/api/strikecast_api/main.py; core package owns API schemas and the runtime risk/model boundary. |
| ARCH-002 | MEDIUM | DOCUMENTED_NOT_CONSOLIDATED | Research and training trees contain separate ConvLSTM/model and trainer implementations from the served core; they are retained for experiments and are not interchangeable. |
| ARCH-003 | HIGH | BLOCKED | No canonical raw ERA5/LIS paired dataset builder exists. The guarded CLI is demo-only and strict prepared-data loader is not a provider adapter. |
| ARCH-004 | MEDIUM | OPEN | API rate limiter is process-local memory and does not protect a multi-worker deployment consistently. |
| ARCH-005 | HIGH | OPEN | Development launcher enables reload and binds 0.0.0.0; it must not be treated as production deployment. |
| ARCH-006 | MEDIUM | ENVIRONMENT_LIMITATION | No Git metadata is present in this checkout; commit-based provenance and working-tree diff cannot be verified. |
| ARCH-007 | MEDIUM | DOCUMENTED | ZIP inventory validates metadata/CRC without extraction; no canonical safe extraction utility is present. Any future extraction requires containment and expansion limits. |
| ARCH-008 | MEDIUM | OPEN | Python requirements are not a complete hash-locked environment; web app has package-lock.json. Dependency audit required. |
| ARCH-009 | MEDIUM | DEMO_ONLY | The verified checkpoint loader currently approves only a hardcoded demo artifact digest and metadata; there is no generic signed candidate registry. |
| ARCH-010 | LOW | SAFE_BLOCKED | No automated production model promotion is configured; candidate acceptance is BLOCKED and production model slot is empty. |
| ARCH-011 | MEDIUM | OPEN_REVIEW | API middleware logs rounded location buckets; retention/privacy requirements should determine whether this telemetry is necessary. |
| ARCH-012 | MEDIUM | OPEN_REVIEW | Runtime API response schema validation is delegated to FastAPI response_model; failures are generic 500 but no dedicated response-contract test covers every endpoint. |

## Security scan

Secret scanner status: **NOT_FOUND_BY_CONFIGURED_HEURISTICS** (0 high-confidence matches). See `SECRET_SCAN_REPORT.md`; no matched values are emitted. Heuristics do not prove absence of secrets.

Archive intake currently inspects ZIP metadata and CRC without extracting members; safe extraction is not implemented or needed by this workflow. Strict NPZ loading disables pickle and verifies path/checksum. API CORS disallows wildcard credentials; body limits and baseline headers exist. Distributed rate limiting, production launch configuration, signed artifacts and a full penetration review remain open.

## Repository inventory

- `apps/api`: 7 files (generated directories excluded)
- `apps/web`: 38 files (generated directories excluded)
- `packages/strikecast_core`: 26 files (generated directories excluded)
- `ml`: 83 files (generated directories excluded)
- `data`: 1155 files (generated directories excluded)
- `artifacts`: 36 files (generated directories excluded)
- `configs`: 11 files (generated directories excluded)
- `scripts`: 24 files (generated directories excluded)
- `tests`: 64 files (generated directories excluded)
- `docs`: 47 files (generated directories excluded)
- `infra`: 2 files (generated directories excluded)
- `.github`: 2 files (generated directories excluded)

Full observations and scope limitations are machine-readable in `ROUND2_ARCHITECTURE_AUDIT.json`.
