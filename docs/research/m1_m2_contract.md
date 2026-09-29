# M1 → M2 Data Contract

**Owner:** Member 1 — Data Engineering & Multimodal Ingestion
**Consumer:** Member 2 — Spatio-Temporal Processing & Feature Engineering

This is the authoritative interface between M1 and M2. M2 should depend on
this document (and the `DataRecord` / `QualityReport` / `GridSpec` /
`VariableSpec` types in `src/ingestion/contract.py`) and nothing else about
M1's internals — adapter implementations may change without notice as long
as this contract holds.

---

## What data do I (M2) receive?

One `DataRecord` per source per ingestion run, for four sources:

| Source     | Type    | Grid?            | Variables (MVP)                                                        |
|------------|---------|-------------------|--------------------------------------------------------------------------|
| satellite  | gridded | yes               | `brightness_temperature` (K), `cloud_top_height_estimate` (km)          |
| lightning  | point   | no (`point_data`) | `intensity` (kA, signed; sign ~ polarity)                               |
| nwp        | gridded | yes               | `temperature_2m`, `relative_humidity`, `surface_pressure`, `wind_u`, `wind_v`, `cape`, `cin` |
| radar      | gridded | yes               | `reflectivity` (dBZ)                                                    |

All MVP data is **synthetic/demo** (`provenance.is_synthetic == True`). No
real external data source is wired up in this repository — see "Known
limitations" below.

## Where is it stored?

```
data/sample_demo/<source>/<source_id>_<start>_<end>.npz   # bulk array data
data/sample_demo/<source>/<source_id>_<start>_<end>.json  # metadata sidecar
data/sample_demo/metadata/manifest.json                    # run-level index of all 4 sources
```

(Same layout under `data/raw/<source>/` for non-demo runs, once a real
adapter exists — currently unused since real ingestion is not implemented.)

## How do I load it?

```python
from src.ingestion.storage import load_record

record = load_record("data/sample_demo/satellite/mock_geostationary_ir_v1_....npz")
```

or use `data/sample_demo/metadata/manifest.json` to discover the current
file paths for all four sources programmatically (this is the recommended
entry point — don't hard-code filenames, they embed timestamps).

`load_record()` returns a `DataRecord` (see `src/ingestion/contract.py`).

## What variables exist, with what units and dimensions?

See the table above for names/units. Full detail (including `valid_min`/
`valid_max`/`fill_value`/`description`) is in each record's
`.json` sidecar under `"variables"`, and is always re-derivable via
`adapter.get_schema()` for any given source adapter.

**Gridded sources** (`satellite`, `nwp`, `radar`): `record.data` is a numpy
array shaped `[time, lat, lon, variables]`, dtype `float32`. This is
directly compatible with the eventual model tensor shape
`X = [batch, time, latitude, longitude, channels]` once M2 stacks/batches
across sources and windows — M1 does **not** perform that stacking.

**Point source** (`lightning`): `record.data` is `None`; use
`record.point_data`, a `list[dict]` with keys `latitude`, `longitude`,
`timestamp`, `intensity`, `polarity`. M1 does **not** grid/bin lightning
strikes onto the spatial grid — that is an M2 feature-engineering step.

## What timestamps exist?

`record.timestamps` — a `list[str]`, ISO-8601, UTC, suffixed `Z`
(e.g. `"2026-06-01T00:00:00Z"`), sorted ascending, deduplicated. All four
sources in a given demo run share the same timestamp grid (12 hourly steps
starting `2026-06-01T00:00:00Z` by default — configurable in
`config/ingestion_config.yaml`).

## What spatial grid is used?

`record.grid` (gridded sources only) is a `GridSpec`: `lat_min/lat_max/
lon_min/lon_max/lat_resolution_deg/lon_resolution_deg/n_lat/n_lon` plus the
actual `lat_values`/`lon_values` arrays (degrees, WGS84, monotonic
ascending). Default MVP domain: lat 18–22°N, lon 77–81°E, 0.25° resolution
(17×17 cells) — an arbitrary demo region over central India, configurable.

## What does each quality flag mean?

Every `DataRecord.quality` is a `QualityReport`:

| Field                | Meaning                                                                 |
|-----------------------|--------------------------------------------------------------------------|
| `quality_status`      | `ok` / `degraded` / `failed` — the single field to gate on              |
| `coverage_fraction`    | fraction of expected timestamps actually present (temporal gaps reduce this) |
| `missing_fraction`     | fraction of values that are NaN (or a legacy sentinel) across the whole record |
| `valid_fraction`       | fraction of finite values within each variable's documented physical range |
| `schema_status`        | `valid` / `invalid` / `not_checked` (point sources are `not_checked` — no fixed array schema) |
| `issues`               | human-readable list of every problem found (empty if none)              |

Thresholds (in `config/ingestion_config.yaml`, `quality_thresholds`):
`missing_fraction > 0.30` **or** `coverage_fraction < 0.50` → `failed`.
`missing_fraction > 0.05` or any non-empty `issues` → `degraded`. Otherwise `ok`.

**M2 should not consume a `failed` record without explicit handling** —
treat it the way you'd treat a missing file, not a slightly-noisy one.

## What missing values are possible?

Within `record.data`, missing values are represented as `NaN` — never a
sentinel like `-9999` in the M1→M2 output (a `fill_value` field exists per
`VariableSpec` only to document what a *raw upstream format* might use
before M1 normalizes it to NaN during ingestion). `np.isnan()` /
`np.isfinite()` are sufficient; no per-source sentinel lookup is needed.

## What assumptions must I know?

- All four sources currently share one synthetic RNG-seeded generator, are
  spatially/temporally loosely "storm-like" for demo plausibility, but are
  **not physically coupled or scientifically meaningful** — do not draw
  conclusions from correlations between them.
- `dataset_version` is a per-adapter version string (currently
  `"0.1.0-demo"` for all four) — bump it if the demo generator's
  scientific content changes, so M2/M4 can detect stale caches.
- Grid and timestamp parameters are read from
  `config/ingestion_config.yaml` at generation time and are also recorded
  in `manifest.json` for a given run — always check the manifest rather
  than assuming today's config values match a previously-generated file.

## What validation has already happened?

Temporal (ordering, duplicates, gaps, coverage), spatial (range,
monotonicity, resolution), schema (variable count, dtype, per-variable
physical-range check), and missing-data fraction — all folded into
`record.quality`. M2 does not need to re-run these checks, only to read
`quality_status`/`issues` and decide how to handle non-`ok` records.

## What preprocessing is NOT done yet?

Per the M1/M2 boundary below: temporal alignment across sources (they
happen to share a timestamp grid in the demo, but M1 makes no guarantee of
this for real data), spatial regridding/reprojection, missing-value
masking (no two-sided temporal interpolation), normalization/standardization, lightning gridding/binning,
sequence/window construction, and train/val/test splitting. All of that is
M2's job.

---

## The M1/M2 boundary, explicitly

**M1 does:** Acquire · Load · Validate · Standardize metadata · Track
provenance · Store · Expose (via `DataRecord` + `manifest.json`).

**M2 does:** Temporal alignment · Spatial alignment · Missing-value masking ·
Normalization · Feature engineering · Sequence creation · Train/validation/
test splitting.

---

## Known limitations (be honest)

- **No real external data source is integrated.** All four adapters are
  synthetic-only MVP implementations (see each adapter's module docstring
  and the Phase 1 audit in the Phase 13 report). Swapping in a real source
  means implementing a new `load()` for that adapter — `validate()`,
  `get_schema()`, `normalize_metadata()`, and the contract types do not
  need to change.
- Lightning/satellite/NWP/radar are generated independently and are only
  loosely spatially coordinated for demo plausibility — not a physically
  consistent atmospheric state.
- Only one demo region/time window is generated by default; multiple
  scenarios would need either re-running the generator with a different
  config or a small extension to parametrize scenario name into the output
  path (not currently implemented).
