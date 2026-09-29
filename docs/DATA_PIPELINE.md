# Data pipeline and provider interface

## Current intake

Inventory scripts hash source files and inspect NetCDF/GRIB metadata. ZIP inventory checks member names, sizes, CRC and compression metadata without extracting files. The current ERA5/LIS drops have an exact ERA5 acquisition report at `artifacts/reports/ERA5_REQUIRED_COVERAGE.md` and `data/database/manifests/era5_required_coverage.json`. There are no eligible paired real samples; do not train.

## Provider contract

A provider adapter should implement the concepts below while leaving model/API schemas unchanged:

```python
class DataProvider:
    provider_id: str
    schema_version: str
    def inventory(self, source_root): ...  # hashes, files, coverage and license provenance
    def read(self, source_record, window): ...  # values + valid time + availability time + coordinates
    def validate(self, record): ...  # units, physical bounds, coordinate/time integrity, quality
```

Each adapter supplies a schema mapping and a provenance manifest. Canonical records carry source hash, dataset/version, valid time, availability time, coordinates/grid, variable units, quality and validity masks. Reject malformed inputs; do not silently infer provider metadata or treat missing observations as zero.

## Required processing order

1. Inventory and hash every new source file.
2. Validate file type, provider/license, checksum, temporal/spatial bounds, units and product quality.
3. Convert through provider mapping into canonical records with valid and availability timestamps.
4. Align features causally to forecast issue times; retain missingness masks and prohibit future interpolation.
5. Generate targets only where LIS view-time and quality support the entire target interval; unknown remains masked.
6. Persist schema versions, source hashes, preprocessing version and feature/target observation masks.
7. Split full windows chronologically; fit normalization from train only.
8. Run `python scripts/ml/leakage_audit.py --dataset <prepared-dataset>` before any training.

The `real_dataset.py` loader validates prepared NPZ contracts; it is not a provider plugin or raw-pairing implementation. ERA5 availability metadata needs operational review before live forecasting claims.
