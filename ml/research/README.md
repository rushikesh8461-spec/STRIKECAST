# StrikeCast research pipeline

This package contains experimental multimodal ingestion, validation, preprocessing, feature, model and training code. It is not the served inference stack. Canonical local demo serving is `apps/api/strikecast_api/main.py`, backed by `packages/strikecast_core/`.

Research training primitives support synthetic and bundled demo sources for shape/reproducibility tests. Those runs do not create production evidence. A strict manifest/NPZ validator is available at `python scripts/data/validate.py <dataset-dir>` (run from repository root). No accepted real lightning dataset is currently supplied; validation, benchmark, calibration and model promotion are therefore not available.

See `docs/architecture/DECISIONS.md`, `docs/data/DATASET_CONTRACT.md`, and `docs/reports/FINAL_VERIFICATION_REPORT.md` for current boundaries and scientific limitations.
