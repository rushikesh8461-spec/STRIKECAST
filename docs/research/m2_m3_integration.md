# M2 <-> M3 integration

Until this change, M2 (`src/ingestion`, `src/preprocessing`, `src/features`)
and M3 (`src/models`, `src/training`, `src/inference`) were two codebases
that had never been run against each other. `docs/m2_m3_contract.md`
described the interface, but no code called it: `src/training/train.py`
and `src/inference/predict.py` only ever constructed `SyntheticDataset`,
and `SyntheticDataset`'s random tensors — not `build_dataset()`'s real
windows — were what every checkpoint in this repo up to now was trained
and tested on.

This doc describes what closes that gap. The design goal was **zero
changes to model code** — `ConvLSTM`, `FusionConvLSTM`, `losses.py`,
`checkpoint.py` are untouched. Everything lives in a new adapter layer.

## What was added

### `src/training/m2_bridge.py` (new)

- `load_m2_bundle(preprocessing_config_path=None, demo=True)` — thin,
  lazily-imported wrapper around
  `src.preprocessing.dataset.build_dataset()`. Lazy so that
  `SyntheticDataset`-only workflows never require M2 to be importable.
- `channel_groups_by_source(feature_schema)` — reads the `source` field
  M2 already attaches to every channel
  (`WindowDataset.get_feature_schema()`, e.g. `"radar"` /
  `"radar (derived)"`) and groups channel indices by base source. This is
  what lets `FusionConvLSTM` receive M2's single stacked
  `[T, H, W, C]` tensor split back into one tensor per source
  (satellite / nwp / radar / lightning on the bundled demo data — 3 / 10 /
  3 / 3 = 19 channels) with no hardcoded channel names or counts anywhere.
- `M2Dataset` — wraps one M2 `WindowDataset` split as a
  `StrikeCastDataset` for single-input models (ConvLSTM, classical_ml,
  persistence). Implements exactly the transform
  `docs/m2_m3_contract.md` describes:
  - `X: [L, lat, lon, C]` (M2) → `torch [L, C, lat, lon]` (M3, via
    `.permute(0, 3, 1, 2)`)
  - `y: [H, lat, lon]` (M2) → `torch [H, 1, lat, lon]` (M3, via
    `.unsqueeze(1)`)
- `M2MultimodalDataset` — same, but returns `dict[str, Tensor]` for
  `FusionConvLSTM`, one `[T, C_m, H, W]` tensor per source.
- `build_m2_dataset(window_dataset, contract, multimodal)` — picks
  between the two above.

`mask` (`[L, lat, lon, C]`, bool) is deliberately **not** part of the
`(x, y)` tuple these classes return — that would break the
`StrikeCastDataset.__getitem__` contract every training-loop call site
relies on, and `docs/m2_m3_contract.md` is explicit that the MVP baseline
doesn't need it ("any window with too high a missing fraction has already
been dropped"). It's still reachable via `M2Dataset.get_mask(idx)` for
anyone building masked-loss training later.

### `DataContract.from_m2_bundle(bundle, multimodal=False)` (in `src/training/config.py`)

Builds a real `DataContract` (`sequence_length`, `height`, `width`,
`forecast_horizon`, `target_type`, and either `input_channels` or
`modalities`/`modality_channels`) directly from a loaded M2 bundle,
instead of the YAML `PLACEHOLDER` values. `target_type` is derived from
M2's `target.mode` config (`"occurrence"` → `"binary"`, `"strike_count"`
→ `"continuous"`) rather than assumed.

### `TrainConfig.data_source` (`"synthetic" | "m2"`)

New field, plus `m2_preprocessing_config` (path override) and `m2_demo`
(bool). `train.py`'s `build_dataloaders()` and `predict.py`'s inference
functions branch on it. Checkpoints already save the full `TrainConfig` as
plain dicts (`checkpoint.py`), so a checkpoint trained with
`data_source: "m2"` carries that fact — `predict.py` reproduces the same
kind of data (real M2 windows, not a synthetic stand-in) by default at
inference time, unless overridden with `--data-source`.

### `train.py` / `predict.py` changes

- `train_nn_model`: dataloaders are now built **before** the model, when
  `data_source == "m2"`, because building the M2 dataloader is what
  replaces the placeholder `DataContract` with the real one the model
  needs to be sized against (real channel count, real grid size).
  This ordering is a no-op when `data_source == "synthetic"`.
- Both the epoch loop and `run_inference_nn`/`run_inference_classical`
  handle the **documented 0-val/0-test-windows case** (bundled demo data
  has only 12 timesteps — see `docs/m2_m3_contract.md` "Known
  limitation") without dividing by zero or crashing: validation is
  skipped with a printed warning, and inference falls back to the
  `train` split with a printed warning if the requested split is empty.
- `train_classical` and `run_inference_classical` got the same
  `data_source` branch, for consistency (the M3 checklist's "Baselines
  work" item covers classical_ml too, not just ConvLSTM).

### New configs

- `configs/convlstm_m2.yaml`, `configs/fusion_m2.yaml` — same
  hyperparameters as the existing `*_default`/`*_example` configs, with
  `train.data_source: m2`. Their `data:` blocks are documented as
  fallback-only, since `config.data` gets replaced by
  `DataContract.from_m2_bundle()` at runtime.

### Bug fix unrelated to the adapter itself, found while integrating

`PreprocessingConfig.data_root` and `IngestionConfig.data_root` resolved
the config's relative `paths.data_root: "data"` against the **current
working directory** (`Path(...).resolve()`), not the repository root —
inconsistent with how those same two files already resolve their own
default *config file* path (`Path(__file__).resolve().parents[2]`). In
practice this meant `build_dataset()` (and hence the new M2 training path)
silently broke — `FileNotFoundError` looking for `data/sample_demo/...` —
whenever a training/inference command was run from any directory other
than the repo root. Fixed by anchoring a relative `data_root` to the repo
root the same way the config-file lookup already does; an absolute
`data_root` in the config is still honored unchanged. Verified by running
`build_dataset()` from `/tmp` before and after the fix.

## What was intentionally left alone

- Model architectures (`ConvLSTM`, `FusionConvLSTM`, `ClassicalMLBaseline`,
  `PersistenceBaseline`) — no changes.
- `ModelOutput` / `losses.py` / `checkpoint.py` schemas — no changes.
- `SyntheticDataset` and the `synthetic` data path — untouched; still the
  default, still what the pre-existing unit tests in
  `tests/models_pipeline/` exercise.
- M2's preprocessing logic itself (alignment, normalization, feature
  engineering, splitting) — no changes beyond the `data_root` fix above.

## Known limitations that are now visible (not hidden) rather than fixed

- **Bundled demo data yields 0 val / 0 test windows.** This is an M2-side,
  already-documented limitation (`docs/m2_m3_contract.md`), not something
  this integration works around. Training on `configs/convlstm_m2.yaml` /
  `configs/fusion_m2.yaml` proceeds on the 3 train windows and prints a
  warning instead of crashing; there is currently no real validation
  signal on the bundled demo data. To get non-empty val/test, regenerate
  the demo data with a larger `sample_demo.n_timestamps` (see
  `config/ingestion_config.yaml` and `docs/m2_m3_contract.md`).
- **`ClassicalMLBaseline` requires `forecast_horizon == 1`** — already
  true of M2's default config, so no conflict today, but a config change
  to `forecast_horizon > 1` will raise `NotImplementedError` from
  `classical_ml.py`, not from the bridge.
- This integration was implemented and its non-torch surface (channel
  grouping logic, and `build_dataset()`'s real output shapes) was
  verified by direct execution in the environment this was written in.
  The torch-dependent surface (`M2Dataset`/`M2MultimodalDataset`,
  `train_nn_model` on real data, the new tests in
  `tests/models_pipeline/test_m2_integration.py`) was verified by a
  side-by-side pure-NumPy dry run of the exact same tensor transforms
  against the real bundle (matching shapes and channel-count arithmetic),
  **not** by running the torch code itself — torch was not installable in
  that environment. Run `pip install -r requirements.txt && python -m
  pytest tests/models_pipeline/test_m2_integration.py -v` to get the real
  first run.
