# Training run report

Status: **BLOCKED BEFORE FIT**. The data gate found 650 required ERA5 input hours, of which 646 are missing, and no prepared real paired dataset. There are no train windows with validated observation masks.

- Training executed: **NO**.
- Model/checkpoint: no candidate created; existing demo checkpoint was not modified.
- Training/validation loss, learning-rate history, class weighting, early stopping, and resume state: **NOT RUN**.
- Dataset version: `NOT_CREATED_BLOCKED`.
- Random seed: no fit occurred.

Exact missing ERA5 dates/hours and variables are listed in `ERA5_REQUIRED_COVERAGE.md` and `era5_required_coverage.json`. Satisfying ERA5 coverage alone is not sufficient: acquire/verify LIS observation coverage for complete target intervals and construct target observation masks before training.
