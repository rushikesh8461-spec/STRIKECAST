# ML pipeline readiness

The intended stages are dataset contract validation, leakage audit, train-only normalization, masked training, validation-only model selection/calibration, untouched test evaluation, checkpoint integrity and acceptance. Current real-data readiness stops before sample construction: 0 eligible samples in train/validation/test and 646 of 650 required ERA5 predictor hours missing from at least one product. `scripts/ml/train.py` only accepts demo sources and refuses non-DEMO mode.

`target_observation_mask_<split>` is required. False mask entries are UNKNOWN and excluded from loss and metrics. The prepared loader requires observed positives and negatives within each split, verifies chronology/availability/normalization/provenance fields, and rejects duplicates. It cannot independently validate upstream provider truth or construct target masks.

Run readiness with `python scripts/ml/run_real_pipeline_audit.py`. Run leakage checks with `python scripts/ml/leakage_audit.py`; with no eligible real manifest, the expected state is BLOCKED and exit code 2. Do not launch synthetic research trainers as a substitute for the guarded CLI.
