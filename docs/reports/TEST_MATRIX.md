# Test matrix

| Area | Scope | Evidence |
|---|---|---|
| Shared core | Data, point feature tensor, model loading, risk and evaluation utilities | `tests/unit/` |
| API/security | Request validation, errors, provider safety, model unavailable behavior | `apps/api/tests/` |
| Research | Ingestion, schema, leakage, splits, normalization, training primitives and legacy compatibility | `tests/research/strikecast/` |
| API integration | Health, metadata, deterministic DEMO, risk/lightning and LIVE refusal | `scripts/development/smoke_test.py` |
| Configuration/structure | YAML parse and monorepo boundaries | `scripts/development/validate_configuration.py`, `scripts/development/validate_structure.py` |
| Web | TypeScript, unit tests, production build, mocked browser flows | `apps/web/` npm scripts |

The latest counts and environment limitations are in [the verification report](VERIFICATION_REPORT.md) and [`artifacts/reports/final_check.json`](../../artifacts/reports/final_check.json). Passing tests do not measure forecast skill.
