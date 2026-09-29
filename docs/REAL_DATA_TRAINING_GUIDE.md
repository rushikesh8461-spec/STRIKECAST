# Real-data intake and training guide

## Current disposition

The uploaded archives are preserved under `data/raw/`; extracted GRIB members are in `data/interim/`. The repeatable metadata inventory is:

```powershell
python -m pip install -r requirements-data.txt
python scripts/data/inventory_uploaded_data.py
```

The inventory is metadata-only. It does not construct samples or labels. The LIS audit found 177 domain-intersecting granules over 76 dates. Existing 2023 ERA5 single- and pressure-level data overlap only 2023-11-16, when one domain-intersecting LIS granule provides a short pass rather than a complete one-hour observed target. The exact requested ERA5 hours are listed in `artifacts/reports/ERA5_REQUIRED_COVERAGE.md`; 646 of 650 required hours are currently absent from at least one of the two ERA5 products. 2025 ERA5 is not a substitute. Do not train or calibrate from these files.

For real targets, persist the LIS target-observation mask alongside the target array. A zero event count is a negative only where view-time coverage and quality checks establish that the location and target interval were observed. Unobserved cells must remain masked/unknown. The strict prepared-data loader requires `target_observation_mask_<split>` and checks class diversity using observed cells only.

## Requirements before pairing

1. Record each provider download request, source DOI/version, product, license/terms, checksum, variables, cadence, grid, and time convention. The LIS filenames say V3.0, but the available NASA guide documents older product revisions; obtain the matching V3.0 data dictionary.
2. Obtain co-located ERA5 single-level and pressure-level periods matching many LIS overpasses, not merely the same calendar date. For operational/live claims, use forecast/issue-time-available predictors rather than retrospective ERA5 analyses; record each field's availability time.
3. Parse LIS view-time intervals, flash/event times, alert flags, and quality tags. Only label observed coverage. A no-flash cell may be negative only when valid view time covers the entire target interval. Keep all other cells masked/unknown.
4. Define the spatial cell aggregation and exact one-hour target interval (boundary convention included). Preserve LIS's native 0.5-degree observation footprint; aggregate ERA5 to that support or use a physically justified area-weighted mapping. Do not upsample LIS to imply 0.25-degree observations.
5. Require enough continuous/event-diverse periods for chronological train/validation/test with whole forecast windows and storm groups separated. If fewer than 10,000 samples are produced, report the actual count; do not duplicate or synthesize labels.
6. Fit normalization on TRAIN only. Compare climatology, eligible persistence, logistic regression, and tree baseline on VALIDATION. Freeze candidate/calibration/threshold before one-time TEST evaluation. Run [`scripts/ml/validate_model_acceptance.py`](../scripts/ml/validate_model_acceptance.py) only after independent evidence review.

The current research baseline comparison expects a prepared dataset with a complete provenance manifest and strict paired NPZ schema; see [`DATASET_CONTRACT.md`](data/DATASET_CONTRACT.md). A raw GRIB/NetCDF-to-valid-paired-sample builder is intentionally not claimed by the inventory script. Add and validate that builder only after temporal target and quality semantics are approved.
