# Final system verification

Date: 2026-09-28. Existing architecture remains frozen. The new read-only `NEW DATA/` source was ingested and hashed. The external collection contains 1,550 LIS paths with 1,130 distinct byte contents (including one empty-file hash); the canonical raw inventory now contains 1,134 paths. Metadata-based filtering finds 177 domain-intersecting readable LIS granules across 76 observation dates. Both ERA5 products are available together only on 2023-11-16; the exact 650 predictor-hour requirement and 646 missing hours are in [`ERA5_REQUIRED_COVERAGE.md`](ERA5_REQUIRED_COVERAGE.md). The latest Python-suite result is recorded in [`FINAL_VERIFICATION_REPORT.md`](../../docs/reports/FINAL_VERIFICATION_REPORT.md); source lineage is in [`historical_lis_ingestion.json`](../../data/database/manifests/historical_lis_ingestion.json), and the 10K data requirement is documented in [`DATA_REQUIREMENT_FOR_10K.md`](DATA_REQUIREMENT_FOR_10K.md).

| Area | Status | Evidence / limitation |
|---|---|---|
| Uploaded-file inventory | PASS WITH INVALID INPUTS RECORDED | 1,134 canonical raw paths: 1,131 LIS paths + 3 ERA5 archives; 1,128 unique LIS files opened and yielded metadata, one exact duplicate raw path, one empty representative, and one unreadable HDF5 file. The incoming-source manifest records 1,550 paths, 420 repeated-content paths, and 59 zero-byte paths. |
| Workspace duplicate copy | PASS / DEDUPLICATED | One extra project-root copy of the 2025 ERA5 ZIP is byte-identical to the canonical archive and Downloads original; recorded separately and not counted as a new dataset. |
| Historical LIS ingestion | PASS / ERA5 STILL MISSING FOR NEW DATES | 1,123 new source hashes copied to raw (1,122 non-empty); added LIS dates lack matching ERA5 outside 2023-11-16. |
| Data quality for supervised task | BLOCKED | No valid one-hour paired labels, no multi-period common coverage, source acquisition/version/license needs confirmation. |
| Research model | DEMO_ONLY | No real-data model trained or registered. |
| Calibration/held-out evaluation | NOT RUN | No eligible splits/predictions. |
| Model acceptance/LIVE | BLOCKED | Existing acceptance record remains BLOCKED; LIVE remains disabled. |
| Python suite | PASS | Re-run after ingestion/scanner changes: `python -m pytest -q`, 348 passed, 0 failed, 7 warnings in 71.92 seconds (2026-09-28). |
| API | PASS, DEMO only | Local Uvicorn health, metadata, predict, and risk returned HTTP 200. Invalid coordinates and unexpected fields returned HTTP 422; request ID and security headers were present. |
| Frontend unit tests | PASS | Re-run `npm test`: 9 passed. |
| Frontend typecheck/build | PASS | Re-run `npm run typecheck` and `npm run build`; Vite emitted a 1.77 MB chunk advisory. |
| Playwright | PASS | Re-run `npm run test:e2e`: 5 passed. |
| Dependency audit | INCOMPLETE | `npm audit` could not verify the registry certificate. `pip-audit` did not complete. TLS verification was not bypassed. |
| End-to-end real-data workflow | BLOCKED | Stopped at label validity; training/evaluation/API real model integration is not scientifically supportable. |
| API security residuals | PARTIAL | Existing API tests and prior local smoke pass; production body-byte limits, rate limits, and full security review remain open. No accepted model or LIVE mode. |

The project must not present the supplied observation window as a historical prediction-vs-observation test case or show the demo model as a real-data forecast.

## Required verification matrix

### Data

| Item | Result |
|---|---|
| ERA5 single-level files | PASS inventory; 2023 matching day plus 2025 non-overlapping period |
| ERA5 pressure-level files | PASS inventory for 2023-11-16 only |
| LIS files | PASS WITH 2 INVALID UNIQUE INPUTS | 1,128 unique granules readable; 59 zero-byte source paths deduplicated to one empty raw representative, one 12,699-byte HDF5 read error, and one exact duplicate old raw path |
| Common temporal period | LIS orbit starts 2023-07-05–2023-11-16; both ERA5 products overlap only on 2023-11-16 |
| Common spatial rectangle | 8–20 N, 72–82 E; one LIS orbit, 345 distinct view-time centers; per-cell view-time union max 111 seconds |
| Pairing / valid unique samples | FAIL for hourly supervised target; 0 valid samples |
| 10,000 sample target | FAIL / unsupported by uploaded coverage |
| Positive / negative / unknown hourly cell labels | 0 / 0 / 525 candidate cells unknown for the one intersecting pass |
| Data quality | PARTIAL; file integrity/readability PASS, provenance/license/flag review and full physical-value audit incomplete |

The additional-data gate remains 10,000 valid unique labeled cell-time samples. Current valid count is zero. The duration needed cannot be estimated from the sparse inputs; additional co-located, quality-valid LIS observation periods and causal ERA5 surface/pressure histories are required. See `DATA_REQUIREMENT_FOR_10K.md`.

### ML

| Item | Result |
|---|---|
| Baseline implementations | PASS in software; real benchmark not run |
| ConvLSTM | BLOCKED for real training |
| Pressure-level model / feature ablation | BLOCKED |
| Leakage audit | BLOCKED for a real dataset; no paired samples built |
| Chronological split | BLOCKED; insufficient coverage |
| Calibration / held-out test | NOT RUN |
| Model acceptance | BLOCKED; acceptance record remains blocked |

PR-AUC, ROC-AUC, Brier, log loss, precision, recall, F1, CSI, POD, FAR, ECE, and confusion matrix are all **NOT AVAILABLE**; no test predictions exist.

### System

| Item | Result |
|---|---|
| API health / metadata / predict / risk | PASS, DEMO mode; HTTP 200 |
| Invalid coordinates / unexpected fields | PASS safe HTTP 422 |
| Request ID / security headers | PASS observed on live local server response |
| Frontend unit tests / typecheck / build | PASS: 9 tests, typecheck, build (bundle advisory) |
| Playwright | PASS: 5 tests |
| Python suite | PASS: 348 tests |
| Dependency audit | INCOMPLETE: npm registry TLS verification failed; pip-audit did not complete |

### Model status

`DEMO_ONLY`. No `VALIDATED_RESEARCH` or `ACCEPTED_PRODUCTION_CANDIDATE` exists. LIVE remains `BLOCKED`.
