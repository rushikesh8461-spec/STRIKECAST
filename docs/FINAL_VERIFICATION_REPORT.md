# Final verification report

## Status

**PARTIAL / READY FOR REAL-DATA INGESTION WORK; NOT READY TO TRAIN OR DEPLOY AS A VALIDATED FORECAST.** The demo model remains `DEMO_ONLY`. Real-data model fitting is deliberately blocked until complete atmospheric coverage and a provenance-complete paired dataset exist.

## Data and ERA5 coverage

The metadata-based LIS inventory contains 1,128 readable unique granules; 177 intersect the StrikeCast domain across 76 observation dates. The regenerated ERA5 planner requires 650 causal input hours. Only four hours have every required surface and pressure-level field: **2023-11-16 08:00, 09:00, 10:00, and 11:00 UTC**. The remaining **646 hours are missing or incomplete**. The 2025 ERA5 archive is reported as extra coverage and does not substitute for the 2023 LIS periods.

The exact required, available, missing, invalid, and extra timestamps, fields, levels, archive hashes, and file statuses are in [`era5_required_coverage.json`](../data/manifests/era5_required_coverage.json) and [`ERA5_COVERAGE_STATUS.md`](../artifacts/reports/ERA5_COVERAGE_STATUS.md). The source LIS coverage audit remains at [`era5_required_coverage.json`](../data/database/manifests/era5_required_coverage.json).

No provenance-complete real paired training dataset exists. The adapters decode actual GRIB/ZIP and LIS NetCDF source records. `packages/strikecast_core/data/real_pipeline.py` connects those records to schema-driven ERA5 grids, conservative half-open LIS observation/target grids, causal feature windows, paired samples, chronological whole-window splits, train-only normalization, masked ConvLSTM training, validation model selection, test metrics, validation-only Platt calibration, baselines, and checksummed candidate artifact validation. A tiny real-format GRIB+NetCDF fixture covers the path; its model metrics are explicitly mechanics-only. The production command still exits before fitting with current coverage and never substitutes demo/2025 data. The trained grid model’s 53-channel [time, height, width] contract does not match the served API’s fixed 8-channel, 6-step, 3x3 point model; candidate API loading remains a code blocker.

## Verification executed

- Python: **375 passed**, 9 warnings, including the real-format GRIB/NetCDF pipeline fixture and temporary candidate artifact validation.
- API smoke: passed, including `/health`, `/ready` (demo is blocked), metadata, deterministic demo predict, risk, lightning, and LIVE fail-closed behavior.
- Frontend: typecheck passed, 9 unit tests passed, 5 E2E tests passed, production build passed. Lazy loading reduced the initial JavaScript bundle to about 245 KB; the map chunk remains about 1.04 MB and is loaded on demand.
- Configuration validation: 17 YAML/workflow files passed; configuration JSON scan found no JSON configuration files.
- Secret-pattern scan: no configured high-confidence patterns found in 342 scanned text files; this is heuristic evidence only.
- Demo checkpoint: pinned checksum and safe-load validation passed; this does not validate scientific skill.
- Dataset validation and leakage audit: `BLOCKED_NO_DATA`; no model fit occurred.
- ERA5 coverage planner: completed with 4/650 required hours available, 646 missing/incomplete, no invalid ERA5 archives, and 6,640 extra hour/product records (including unrelated time coverage).
- Docker runtime and Ruff are unavailable locally. Compose YAML parses; no image build was run.
- This checkout has no Git metadata. Dependency vulnerability audit status is in [`DEPENDENCY_AUDIT.json`](../artifacts/reports/DEPENDENCY_AUDIT.json).

The master verification output is [`ROUND2_FINAL_READINESS_REPORT.md`](../artifacts/reports/ROUND2_FINAL_READINESS_REPORT.md) and its JSON companion. The master `--all` command completed with 16 verification checks and 0 code failures, then returned `BLOCKED_NO_DATA` as expected. The remaining API compatibility gap is a code blocker: the served demo point model expects 8 channels × 6 steps × 3×3, while the real grid model uses configured ERA5 channels and domain dimensions. LIS fatal-flag parsing also requires scientific owner approval before real labels are accepted. No production readiness is claimed.
