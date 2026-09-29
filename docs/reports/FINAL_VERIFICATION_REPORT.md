# Final verification report

Date: 2026-09-28. This report records the latest migration recovery run only. It verifies software behavior and repository structure; it does not establish forecasting skill or production readiness.

## Result

| Area | Result | Evidence |
|---|---|---|
| Architecture/migration | PASS / COMPLETE | Frozen layout; validator confirms unique served API, core schema, model, risk engine, and checkpoint loader |
| Python | PASS | Latest root run: 348 passed, 0 failed, 0 skipped; 7 dependency warnings. |
| API | PASS | 22 API tests and in-process health, metadata, predict, risk, lightning, deterministic DEMO, and LIVE fail-closed smoke |
| Configuration | PASS | 12 YAML configuration/workflow files parsed |
| Security regression | PASS, partial assurance | Existing API suite plus 2 lightning security tests passed; safe checkpoint verifier passed; no Ruff or pip-audit installed |
| Frontend | PASS | This pass: 9 unit tests, typecheck and production build passed; Vite reported a large-chunk advisory |
| Playwright | PASS | This pass: 5 browser tests passed for search, risk rendering, unavailable weather/lightning states, and API failure handling |
| npm audit | NOT COMPLETED | Registry audit endpoint failed TLS certificate verification; TLS checks were not bypassed |
| Docker | UNVERIFIED | Docker CLI unavailable; paths and references reviewed statically |
| CI | UNVERIFIED | Current workflow paths reviewed statically; hosted CI not run |
| Generated files | CLEAN | Python caches, pytest caches, frontend dependencies/build output, and Playwright results removed after verification |

The latest `python -m pytest -q` completed with 347 passed in 24 seconds. The separate `packages/strikecast_core/` invocation reports no tests in that source directory; the root suite covers the core through `tests/` and API tests. The current hardening pass did not rerun frontend or browser checks; their prior results remain as recorded above and frontend sources were not changed.

## Scientific and deployment status

| Item | Status |
|---|---|
| Model | `DEMO_ONLY` |
| Dataset | `NOT_VALIDATED` |
| Held-out evaluation | `NOT_ESTABLISHED` |
| Calibration | `NOT_VALIDATED` |
| Risk thresholds | Provisional, uncalibrated |
| LIVE forecast | `BLOCKED` |

The demo checkpoint SHA-256 is `63150034a809d39a4f60f0003f1de7786d7e9a51457c114adc02a25123ce8cfb`. Its manifest now records dataset `synthetic/demo`, dataset version `not independently released`, and status `DEMO_ONLY`. No accuracy, F1, PR-AUC, Brier, ECE, CSI, POD, FAR, latency, or operational performance claim is made.

The research path now provides a strict paired dataset contract/loader, causal missing-value handling, train-only normalization requirements, chronological whole-window splits, validation-only baseline comparison (climatology, named-channel persistence, logistic regression and histogram gradient boosting), evaluation/calibration utilities, and a fail-closed model acceptance record. These code paths have software tests, including a synthetic fixture integration test. No eligible real paired dataset is present, so real-data benchmark, final evaluation, calibration review, model selection and promotion remain blocked.

Detailed executed results are in [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md) and the current path-sanitized [`final_check.json`](../../artifacts/reports/final_check.json). The full repository tree is [`repository_tree.txt`](../../artifacts/reports/repository_tree.txt).
