# Round 2 readiness runbook

## Current gate

Current state: DATA `BLOCKED`, TRAINING `BLOCKED_BEFORE_FIT`, MODEL `DEMO_ONLY`. There are 0 eligible real samples per split, and 646/650 required ERA5 predictor hours are missing from at least one required product. Do not use the 2025 ERA5 archive to fill 2023 gaps.

## When new data is added

1. Add files under approved raw provider directories; preserve original files and licensing/acquisition records.
2. Run `python scripts/data/inventory_uploaded_data.py`; inspect the resulting inventory and resolve checksum, file-type, coverage, unit, product-version and quality failures. This command inventories; it does not safely extract ZIP contents or build training pairs.
3. Validate provider records through the provider-specific adapter. A provider adapter, schema mapping, provenance manifest and tests are required before a new source is eligible.
4. Build a canonical prepared dataset with source hashes, availability/valid timestamps, coordinates, feature masks, target observation masks and exact schema versions. No such ERA5/LIS builder currently exists.
5. Run `python scripts/ml/run_real_pipeline_audit.py` and `python scripts/data/validate.py <dataset-path>`; any failure blocks subsequent stages.
6. Run `python scripts/ml/leakage_audit.py --dataset <dataset-path>`. Resolve all leakage failures; do not waive them. CI may use `--allow-blocked` to permit the current no-data state while still failing actual contract errors.
7. Confirm the split contract is chronological and whole windows do not cross splits. Fit normalization only on train and persist exact statistics.
8. Training is not currently wired to accepted real paired data. Do not use research/synthetic trainers as a substitute. Implement and review a real-data trainer that consumes the validated manifest and masked targets before training.
9. After an approved trainer exists, train to a unique immutable run ID, compare baselines on the same masks, calibrate/model-select only on validation, and evaluate once on untouched test.
10. Assemble all registry artifacts and checksums; run safe checkpoint, schema, inference/API, security, reproducibility and acceptance checks. Keep candidate status BLOCKED unless every gate passes.
11. Promotion requires explicit human release approval after complete acceptance. Rollback to a previously approved immutable artifact; currently no production artifact exists.
12. Diagnose BLOCKED using `TRAINING_INPUT_AUDIT.md`, `ERA5_REQUIRED_COVERAGE.md`, the prepared dataset validator output, and the leakage audit JSON. Distinguish missing data from schema/quality failures.

Never create labels from missing cells, copy 2025 hours into 2023, disable TLS verification, or overwrite the demo checkpoint.
