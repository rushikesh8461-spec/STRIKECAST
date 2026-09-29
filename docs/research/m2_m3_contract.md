# M2 → M3 Data Contract

Written by M2 (Spatio-Temporal Processing & Feature Engineering) for M3
(AI/ML & ConvLSTM Development). If anything here is ambiguous or doesn't
match what the ConvLSTM implementation actually needs, that's an M2 bug —
open an issue against `src/preprocessing/` / `src/features/`, don't work
around it in M3.

## How do I get a dataset?

```python
from src.preprocessing.config import load_config
from src.preprocessing.dataset import build_dataset

bundle = build_dataset(load_config())   # demo=True by default (bundled sample_demo data)
train_ds = bundle.splits["train"]
val_ds   = bundle.splits["val"]
test_ds  = bundle.splits["test"]

sample = train_ds[0]
X, y, mask = sample["X"], sample["y"], sample["mask"]
```

Or persist a run to disk (`data/processed/`) and re-load the arrays directly:

```bash
python -m src.preprocessing.pipeline
```

writes `train.npz` / `val.npz` / `test.npz` (each with `X`, `y`, `mask`
arrays stacked across that split's windows), `normalization_stats.json`,
and `dataset_metadata.json` (full reproducibility record — see below).

`WindowDataset` (returned per split) is plain Python + numpy — no
PyTorch/TensorFlow dependency is imposed by M2. Wrapping one in a
`torch.utils.data.Dataset` is a one-line adapter:

```python
class TorchWrap(torch.utils.data.Dataset):
    def __init__(self, wd): self.wd = wd
    def __len__(self): return len(self.wd)
    def __getitem__(self, i):
        s = self.wd[i]
        return torch.from_numpy(s["X"]), torch.from_numpy(s["y"])
```

## What shape is X, and what does each dimension mean?

```
X.shape == [sequence_length, n_lat, n_lon, n_channels]
```

(`build_dataset()` returns one window at a time; stack `sequence_length`
windows via a DataLoader/batch collate step in M3 to get the
`[batch, time, lat, lon, channels]` shape from the project brief.)

- **sequence_length** (`config/preprocessing_config.yaml` →
  `sequence.sequence_length`, default **4**): number of past timesteps.
- **n_lat, n_lon**: the target grid's dimensions — read them from
  `bundle.metadata["target_grid"]` (`n_lat`, `n_lon`,
  `lat_resolution_deg`, `lon_resolution_deg`), never hard-code them; the
  demo grid is 17×17 but this is a config value (`spatial_alignment.target_grid`
  in the config, or "whatever the M1 gridded sources share" if unset).
- **n_channels**: `len(bundle.channel_names)` — 19 at the default config
  (12 base + 7 derived; see the channel table below). Toggle derived
  channels via `features.enabled_derived_features` in the config; base
  channels always included.

`X` values are z-score normalized (see "Normalization" below) and contain
**no NaN** — every missing/invalid cell has been filled with
`missing_data.fill_value_after_normalization` (default `0.0`, meaning "at
the training mean" after normalization).

## What shape is y, and what does it mean?

```
y.shape == [forecast_horizon, n_lat, n_lon]
```

- **forecast_horizon** (`sequence.forecast_horizon`, default **1**):
  number of future timesteps predicted, immediately following the input
  window (never overlapping it).
- **Values**: binary lightning occurrence by default
  (`target.mode: "occurrence"` — 1 if
  `lightning_strike_count >= target.occurrence_threshold_strikes` in that
  cell/step, else 0). Set `target.mode: "strike_count"` for the raw
  continuous strike count instead (a regression target).

**Target definition — read this if you're building the model's output
head or loss function.** No target definition existed anywhere in this
repository before M2 (no M3/M4 code, no spec pinned one down) — Phase 1
audit finding: `MISSING — NOT PRESENT IN REPOSITORY`. The gridded-
occurrence definition above is **M2's MVP assumption**, not a requirement
handed down by another member. If M3's architecture or M4's evaluation
metrics need a different target shape/definition (e.g. a single
any-horizon map instead of per-step, or a probability instead of binary),
that's a `src/preprocessing/target.py` change — flag it rather than
reshaping `y` downstream in M3.

## What is `mask`, and do I have to use it?

```
mask.shape == X.shape   # [sequence_length, n_lat, n_lon, n_channels], bool
```

`True` = that `X` cell is an observed value. Temporal gaps are never
interpolated: two-sided interpolation would use later measurements in an
earlier forecast input. `False` = the source observation is missing and the
normalized tensor receives `0.0` as a mean-value stacking placeholder, not a
real reading. The separate mask preserves this missingness.

You don't have to use it for the MVP baseline (any window with too high a
missing fraction — `missing_data.max_missing_fraction_per_window`,
default 25% — has already been dropped entirely, so what remains is
mostly-valid). It's provided so M3 can, if useful, mask the loss/attention
on `False` cells rather than let the model learn from filled placeholders
as if they were real.

## Channel order and definitions

`bundle.channel_names` (equivalently `train_ds.get_feature_schema()`,
which includes full docs per channel) is the authoritative, fixed order —
**base features first, then enabled derived features**, both in the order
declared in `src/features/schema.py`. Reordering
`features.enabled_derived_features` in the config never changes the
resulting channel order (see `tests/features/test_feature_schema.py`).

### Base features (always included)

| # | name | source | units | why |
|---|---|---|---|---|
| 0 | `brightness_temperature` | satellite | K | cold cloud-top anomalies mark deep convection |
| 1 | `cloud_top_height_estimate` | satellite | km | taller tops correlate with stronger updrafts |
| 2 | `temperature_2m` | nwp | K | surface heating drives convective initiation |
| 3 | `relative_humidity` | nwp | % | moisture availability precondition |
| 4 | `surface_pressure` | nwp | hPa | pressure falls often precede convection |
| 5 | `wind_u` | nwp | m/s | shear (with wind_v) organizes/sustains storms |
| 6 | `wind_v` | nwp | m/s | shear (with wind_u) organizes/sustains storms |
| 7 | `cape` | nwp | J/kg | Convective Available Potential Energy (instability) |
| 8 | `cin` | nwp | J/kg | Convective Inhibition (suppression) |
| 9 | `reflectivity` | radar | dBZ | direct precipitation/storm-cell intensity |
| 10 | `lightning_strike_count` | lightning (M2-gridded) | count | recent activity is strongly autocorrelated |
| 11 | `lightning_mean_abs_intensity` | lightning (M2-gridded) | kA | severity signal beyond mere presence |

### Derived features (individually toggleable)

| # (if all enabled) | name | formula | why |
|---|---|---|---|
| 12 | `wind_speed` | `sqrt(wind_u**2 + wind_v**2)` | scalar magnitude, easier for a ConvLSTM than raw u/v |
| 13 | `cape_dt` | causal diff, `cape[t]-cape[t-1]`, 0 at t=0 | rising CAPE is a leading indicator |
| 14 | `cin_dt` | causal diff | CIN eroding toward 0 often precedes onset |
| 15 | `reflectivity_dt` | causal diff | intensifying reflectivity signals a strengthening cell |
| 16 | `brightness_temperature_dt` | causal diff | rapid cooling signals explosive convective growth |
| 17 | `reflectivity_spatial_gradient_mag` | finite-difference gradient magnitude, per timestep | marks storm-cell edges/fronts |
| 18 | `lightning_recent_count_3step` | causal rolling sum, window configurable (default 3) | smooths single-step lightning noise |

Full per-feature `FORMULA/UNITS/DIMENSIONS/WHY` documentation lives in
`src/features/schema.py` (`BASE_FEATURES`, `DERIVED_FEATURES`) — that
module, not this table, is the source of truth if they ever diverge.

**All derived features are strictly causal**: computing the value at
input-timestep `t` uses only base data at times `<= t`. The first step of
any diff/rolling feature is defined as `0` — never wraps around or reaches
outside the array. See `src/features/engineering.py` docstring and
`tests/features/test_feature_engineering.py`.

## Temporal & spatial resolution

- **Temporal resolution**: `bundle.metadata["common_grid"]` records the
  actual number of timesteps and the aligned grid's start/end. The
  resolution itself is either the configured
  `temporal_alignment.target_resolution_minutes`, or (default, `null`)
  inferred as the finest per-source median timestep across all four M1
  sources — never hard-coded.
- **Spatial resolution**: `bundle.metadata["target_grid"]`
  (`lat_resolution_deg`, `lon_resolution_deg`, `n_lat`, `n_lon`). Default:
  whichever grid the M1 gridded sources already share (all four share one
  in the current demo data); override via
  `spatial_alignment.target_grid` in the config to force a different
  domain/resolution.

## Normalization

z-score, `(x - mean) / std`, fit from **TRAIN-split input-timestamps
only** (never val/test, never target-only timestamps) — see
`src/preprocessing/normalization.py` and the leakage-safety regression
test `tests/preprocessing/test_train_only_normalization_statistics.py`,
which plants extreme values only in the val/test time range and proves
they never move the fitted mean/std. Frozen stats are persisted to
`normalization_stats.json` (channel name → `{mean, std}`) for exact reuse
at inference time — always load and apply those saved stats rather than
refitting on new data.

## Train / validation / test split — and a known limitation

Chronological, **PAST → TRAIN → later → VALIDATION → latest → TEST**,
computed on the timestamp index range (`split.train_fraction` /
`val_fraction` / `test_fraction`, default `0.6/0.2/0.2`) — never on window
count. A window is assigned to a split only if its **entire**
input+target index range lies inside that split's range; a window
straddling a boundary is dropped (see
`tests/preprocessing/test_train_val_test_split.py`).

**Known limitation, confirmed by actually running the pipeline against
the bundled data**: the demo dataset (`data/sample_demo/`, generated by
`src.ingestion.demo_generator`) only has **12 timesteps** (M1's
`sample_demo.n_timestamps` config, sized for a quick offline smoke-test,
not for training volume). At the default `sequence_length=4` /
`forecast_horizon=1` (window size 5) and a 0.6/0.2/0.2 split, the val and
test time ranges (3 and 2 timesteps respectively) are each **shorter than
one window**, so `build_dataset()` correctly returns **0 val windows and 0
test windows** on this bundled data — this is not a bug in the split
logic. Proof it isn't: regenerating M1's demo data with
`sample_demo.n_timestamps: 60` (leaving every other config alone) and
re-running `python -m src.preprocessing.pipeline` yields **32 train / 8
val / 8 test** windows. For real training, increase M1's
`ingestion_config.yaml` → `sample_demo.n_timestamps` (or point `demo=False`
at a real ingestion run with more history) — that is an M1 config change,
not an M2 one.

`bundle.metadata["warnings"]` always records exactly what happened (which
windows were dropped and why) for a given run — check it before assuming
a split is non-empty.

## Sequence/window configuration

All of `sequence_length`, `forecast_horizon`, and `stride` live in
`config/preprocessing_config.yaml` → `sequence:` — never hard-coded in
source. Increasing `stride` beyond 1 produces fewer, more time-decorrelated
windows (useful once there's enough history that window overlap becomes a
concern for M4's evaluation).

## Reproducibility metadata

Every `build_dataset()` call returns `bundle.metadata`, and
`python -m src.preprocessing.pipeline` additionally writes it to
`data/processed/dataset_metadata.json`. It records:

- `preprocessing_version` (from `reproducibility.preprocessing_version`)
- `source_dataset_versions` — the exact M1 `dataset_version` string per
  source that produced this run's data
- `common_grid`, `target_grid`, `channel_names`
- `sequence_length`, `forecast_horizon`, `stride`
- `split_boundaries`, `n_windows` per split
- `warnings` — anything dropped and why (straddled-boundary windows,
  too-missing windows, empty splits, unmatched lightning strikes)

`build_dataset()` is deterministic given the same config and input data —
see `tests/preprocessing/test_reproducibility.py` (byte-identical `X`/`y`/
`mask` across repeated calls).

## What M2 does NOT do (M3's job)

- Model architecture (ConvLSTM or otherwise) and training loop
- Choosing a loss function for the target defined above (though flag it
  to M2 if the target shape/definition doesn't fit the architecture)
- Batching/collation beyond one window (`build_dataset()` returns one
  window per `__getitem__`; stacking into `[batch, ...]` is a DataLoader
  concern)
- Evaluation metrics and calibration (M4) or the risk engine (M4)

## Known limitations (be honest)

- **Demo-scale data only.** See "Train / validation / test split" above —
  12 timesteps is a smoke-test volume, not a training volume.
- **Spatial gradient validity is an approximation.** A cell's spatial-
  gradient derived feature technically depends on its neighbors' validity
  too, not just its own; M2 conservatively uses the cell's own validity as
  a proxy (documented in `feature_pipeline.compute_derived_with_validity`)
  rather than tracking full neighbor provenance — judged sufficient for
  an MVP second-order derived feature, not exact.
- **Lightning binning tie-break.** A strike exactly on a grid-cell
  boundary is assigned to the lower-index cell (deterministic, but
  arbitrary) — see `spatial_alignment.bin_lightning_to_grid`.
- **Regridding is nearest-neighbor only**, per the "no heavyweight
  geospatial dependency" instruction — adequate at this repo's dependency
  footprint and the demo's matching-grid data, but a real deployment
  mixing genuinely different native grids may want bilinear/conservative
  regridding (M3/M4, flag if this matters for your evaluation).
- **Rolling-window derived features use a conservative validity rule**:
  any gap anywhere in the rolling window invalidates the whole rolling
  value, with no principled partial-window fallback implemented.

## Future improvements (beyond MVP)

- Bilinear/area-conservative regridding for genuinely mismatched native
  grids (currently nearest-neighbor only).
- Persisted preprocessing cache (recompute avoidance) once dataset volume
  grows beyond one-shot in-memory processing.
- Coordinate with M5 to have `dataset_metadata.json` register with
  MLflow (or whatever M5 standardizes on) instead of being a bare JSON
  file, once M5's tracking approach exists.
- A learned/adaptive target definition, if M4's calibration work shows the
  binary-occurrence MVP target underperforms a probabilistic one.
