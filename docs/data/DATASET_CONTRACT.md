# Canonical paired atmospheric/lightning dataset contract

Contract status: `DEFINED_FOR_RESEARCH_INTAKE`; real ERA5 and ISS-LIS raw files have now been inventoried under `data/raw/`, but there is still no valid paired, labeled dataset. The uploaded files do not support complete one-hour target observation coverage or chronological train/validation/test splits. This contract applies to paired, prepared research datasets; it does not make raw or bundled mock arrays eligible for training or acceptance. See [`DATASET_INVENTORY.md`](../../artifacts/reports/DATASET_INVENTORY.md) and [`REAL_DATA_QUALITY_REPORT.md`](../../artifacts/reports/REAL_DATA_QUALITY_REPORT.md).

## Target and tensor meaning

The canonical research target is version `lightning_occurrence_at_horizon_v1`, as defined in [TARGET_DEFINITION.md](../ml/TARGET_DEFINITION.md): binary lightning occurrence in each grid cell at exactly the selected lead time, where lead time is `forecast_horizon` cadence steps after the final input time. It is not an “any occurrence during the full horizon” target. The initial prepared-archive loader supports one selected lead per example: `X=[N,T,C,H,W]`, `y=[N,1,H,W]`, `timestamps=[N,T]`, `target_timestamps=[N,1]`.

Each `X` feature is in the feature order and units declared by the manifest. The saved `X` payload is finite and already normalized with statistics fitted on TRAIN only. Labels are 0/1 occurrence counts after the declared event-detection and cell-binning procedure. `latitudes[H]` and `longitudes[W]` are WGS84 cell-center coordinates, strictly increasing and regularly spaced. The manifest cadence is in minutes; the target timestamp must equal the final input timestamp plus `forecast_horizon * cadence`.

## Required dataset directory

```text
<dataset-directory>/
├── manifest.json
└── paired.npz
```

Run the validator from the repository root:

```powershell
python ml/research/strikecast/src/ingestion/real_dataset.py --dataset <path-to-dataset>
```

The importable implementation is `ml/research/strikecast/src/ingestion/real_dataset.py`. The loader accepts only a local NPZ payload named directly by its manifest, uses `allow_pickle=False`, verifies SHA-256, and rejects parent traversal. No arbitrary URLs or provider downloads are accepted.

## Manifest fields

Every manifest must include:

| Field | Meaning |
|---|---|
| `dataset_name`, `dataset_version`, `split_version` | Provider-defined dataset identity/version and the deterministic chronological split version; unknown values block acceptance |
| `collection_period` | Ordered timezone-aware UTC start/end for paired source collection |
| `geographic_region` | Named region from source metadata, or `NOT_AVAILABLE` |
| `providers.atmospheric`, `providers.lightning` | Each includes `source`, `provider`, `license`, coverage, variables, units, cadence, spatial resolution, time/geographic range, source checksum, and dataset version |
| `feature_order`, `feature_units`, `feature_version` | Exact ordered model-input schema and units |
| `target_definition`, `target_version`, `forecast_horizon` | Label rule and lead, consistent with [the target definition](../ml/TARGET_DEFINITION.md) |
| `temporal_cadence_minutes`, `spatial_grid` | Regular source time cadence and exact dimensions, bounds, and latitude/longitude degree spacing |
| `missing_value_policy`, `quality_thresholds.max_missing_fraction` | Missing raw observations are rejected or quarantined before preprocessing; prepared invalid inputs are explicitly masked and bounded by a predeclared threshold |
| `preprocessing_version`, `normalization` | Transformation identity and train-only z-score statistics/time range |
| `created_at` | UTC manifest creation timestamp, not the source collection time |
| `quality_gates` | Results for required checks listed below; every gate must be `true` |
| `leakage_protocol` | Normalization fit on TRAIN; calibration, threshold selection, and model selection on VALIDATION; TEST reserved for final evaluation |
| `payload.file`, `payload.sha256` | Direct-child NPZ filename and actual SHA-256 |

`NOT_AVAILABLE` is a provenance value, never an invented provider/version. A manifest with unavailable source, provider, license, version, collection period, feature/target/preprocessing version, or creation timestamp cannot pass model acceptance.

For each split, the NPZ contains `X_<split>`, `y_<split>`, boolean `target_observation_mask_<split>` with the same shape as y, `timestamps_<split>`, `target_timestamps_<split>`, `availability_timestamps_<split>`, and boolean `valid_mask_<split>` with the same shape as X. Target mask false means UNKNOWN; the corresponding y value is only a finite storage placeholder and is never used by loss or evaluation. Both classes must exist among true target-mask cells in every training/evaluation split. Availability timestamps have shape `[N,T,C]` and record when each value was available to the forecaster. All must be timezone-aware and no later than that example's final input timestamp. Invalid feature cells remain identifiable through the feature mask; prepared non-finite values are rejected. Coordinates are shared as `latitudes`, `longitudes`.

The validator checks timestamp timezone/order/cadence/horizon, availability cutoffs, sample duplication, coordinate bounds/spacing/grid shape, finite features and labels, binary labels, strict chronological non-overlapping splits, train-only normalization range, payload checksum, and provenance/gate completeness. Provider physical-range and label-quality checks must be performed on the original unnormalized source data and recorded in the manifest's quality evidence before pairing. This loader cannot independently inspect source archives or prove provider claims; human data governance review remains required.

## Quality gates and leakage controls

Required true gates cover duplicate and monotonic source times, no future leakage, coordinate bounds, physical range checks, missingness, spatial/temporal coverage, label coverage, class balance, feature availability, train-only normalization, validation-only calibration/threshold/model selection, and a test set reserved for final evaluation. The validator independently checks the paired arrays where possible; self-declared gates alone are not scientific evidence.

Preprocessing features must be causal at each input time. Temporal differences/rolling windows use current and prior values only. Two-sided interpolation is prohibited because it uses later observations; missing values stay masked and are mean-filled only after TRAIN normalization for dense tensor compatibility, subject to the configured per-window missingness gate. No random temporal shuffle is permitted. Whole input-plus-target windows must remain in one chronological split.

No valid paired labeled dataset, complete source license/acquisition review, or independent quality review is currently present. Until those exist, scientific training and model acceptance are `BLOCKED — VALID PAIRED DATA REQUIRED`.
