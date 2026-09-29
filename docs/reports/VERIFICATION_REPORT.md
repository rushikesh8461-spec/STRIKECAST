# Verification report

Migration recovery verification date: 2026-09-28. Results below are from commands run in this recovery pass, after the latest schema and checkpoint changes. See [`artifacts/reports/final_check.json`](../../artifacts/reports/final_check.json) for the machine-readable summary.

| Check | Result | Evidence and limit |
|---|---|---|
| Pytest collection | PASS | Latest root run collected 348 tests |
| Root Python suite | PASS | `python -m pytest -q`: 348 passed, 0 failed, 0 skipped, 7 dependency warnings (27 seconds) |
| Separate `tests/` suite | PASS | 306 passed |
| API tests | PASS | 22 passed |
| Core-source test path | NO TESTS | `packages/strikecast_core/` contains no tests; root suite tests core behavior |
| Python compile | PASS | `python -m compileall .` exited 0 |
| Structure | PASS | Required paths, no old roots/caches/machine paths, and unique runtime API/model/risk/schema/checkpoint loader verified |
| Configuration | PASS | 12 YAML files parsed |
| API smoke | PASS | Health, metadata, deterministic DEMO prediction/risk/lightning, and LIVE fail-closed |
| Checkpoint validation | PASS | Safe weights-only load, expected metadata, `DEMO_ONLY`, and SHA-256 verified |
| Security regression | PASS, partial assurance | Full API suite and 2 lightning allowlist tests passed; core checkpoint loader uses weights-only deserialization |
| Frontend typecheck | PASS | `npm run typecheck` |
| Frontend unit tests | PASS | `npm test`: 9 passed |
| Frontend build | PASS with warning | `npm run build` succeeded; Vite warned the JavaScript bundle exceeds its 500 kB advisory threshold |
| Playwright | PASS | `npm run test:e2e`: 5 passed; exercised search, risk layer, unavailable provider states, and API failure behavior |
| npm audit | NOT COMPLETED | Registry endpoint TLS certificate verification failed; no TLS bypass was used |
| Ruff / pip-audit | UNAVAILABLE — NOT EXECUTED | Tools are not installed |
| Docker / Compose | UNVERIFIED | Docker CLI unavailable; Compose, Dockerfile, package, artifact, and entrypoint paths reviewed statically |
| Hosted CI | UNVERIFIED | Workflow paths reviewed statically; no hosted run performed |
| Cleanup | PASS | Generated Python/pytest caches, node_modules, frontend `dist`, and Playwright results removed |

The full Python run completed; the earlier reported pytest stall did not recur. Research code remains separate from the served runtime. The API schema source is `packages/strikecast_core/schemas/api.py`; the API imports it from core without a core-to-API dependency.

The demo model is synthetic/demo-trained. Dataset status is `NOT_VALIDATED`, held-out evaluation is `NOT_ESTABLISHED`, calibration is `NOT_VALIDATED`, risk thresholds are provisional, and LIVE forecasts remain `BLOCKED`. No forecast-skill, calibration, or latency metrics were claimed.
