# Round 2 final readiness report

Status: **READY_FOR_REAL_DATA**

| Check | Status | Exit |
|---|---:|---:|
| repository_audit | PASS | 0 |
| configuration_validation | PASS | 0 |
| secret_scan | PASS | 0 |
| dependency_audit | ENVIRONMENT_BLOCKED | 2 |
| dataset_validation | DATA_BLOCKED | 2 |
| era5_coverage_planner | DATA_BLOCKED | n/a |
| leakage_audit | DATA_BLOCKED | 0 |
| checkpoint_integrity | DEMO_ONLY | 0 |
| python_tests | PASS | 0 |
| api_smoke | PASS | 0 |
| docker_compose_yaml_static | PASS | 0 |
| frontend_typecheck | PASS | 0 |
| frontend_tests | PASS | 0 |
| frontend_e2e | PASS | 0 |
| frontend_build | PASS | 0 |
| docker_runtime | ENVIRONMENT_BLOCKED | n/a |

## External and data gates

- Dataset: **BLOCKED_NO_DATA**; no real training was run.
- Model: **DEMO_ONLY**; no scientific validation or production promotion is claimed.
- ERA5: 4 complete hours available of 650 required; 646 required hours are incomplete.
- Canonical pairing, indexed LIS lookup, bounded input validation, mechanics-tested training/evaluation/calibration, and registry-gated model loading are implemented. Research-grid candidates are explicitly unsupported for point-model serving; incompatible candidates fail closed.
- Full status, exact missing dates, categorized limitations, and environment reasons are in this JSON report and `data/manifests/era5_required_coverage.json`.

## Limitation classification

| Limitation | Type | Can code fix? | Status |
|---|---|---:|---|
| Canonical schema-driven ERA5 gridding, LIS observation grids, masked paired samples, chronological split, train-only normalization and ConvLSTM train/evaluate/calibrate/candidate artifact validation are implemented and fixture-tested. | TYPE_A_CODE | Yes | IMPLEMENTED |
| Research-grid candidates do not satisfy the served point-model feature and normalization contract. They are explicitly marked INFERENCE_COMPATIBILITY=UNSUPPORTED; registry promotion and API loading reject them. Compatible registered point-contract candidates load only through the validated registry pointer. | TYPE_A_CODE | Yes | FAIL_CLOSED |
| 646 required ERA5 hours are missing or incomplete; no provenance-complete real paired training dataset exists. | TYPE_B_DATA | No | BLOCKED |
| Dependency vulnerability scan or Docker runtime may be unavailable in the current environment; results are represented explicitly by individual checks. | TYPE_C_ENVIRONMENT | No | CHECKED |
| LIS quality-flag acceptance and target-viewtime policy must be approved before observed non-lightning can become a negative label. | TYPE_D_SCIENTIFIC | No | OPEN |
