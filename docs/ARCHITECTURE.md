# StrikeCast architecture and canonical ownership

## Status

StrikeCast is a **DEMO_ONLY** service with a research data pipeline that is **BLOCKED** pending eligible real paired samples. The repository is structurally organized as a monorepo, but the full source-to-production ML flow is not implemented or production-verified.

## Canonical ownership

| Capability | Canonical location | Status and boundary |
|---|---|---|
| Served API | `apps/api/strikecast_api/main.py` | Single FastAPI application; returns demo predictions only. |
| Runtime model and inference adapter | `packages/strikecast_core/models/runtime_convlstm.py`, `models/inference.py` | One served ConvLSTM definition; loads only the pinned demo artifact today. |
| API request/response schemas | `packages/strikecast_core/schemas/api.py` | Pydantic request/response contracts. |
| Prepared dataset contract/loader | `docs/data/DATASET_CONTRACT.md`, `ml/research/strikecast/src/ingestion/real_dataset.py` | Strict NPZ + manifest loader; not a raw-provider builder. |
| Target semantics | `docs/data/TARGET_DEFINITION.md`, `ml/research/strikecast/src/preprocessing/target.py` | Positive/negative/unknown plus explicit observation mask. |
| Real-data feature schema | `configs/data/feature_schema.yaml` | Candidate ERA5 mapping; accumulation semantics still require validation. |
| Readiness gate | `scripts/ml/run_real_pipeline_audit.py` | Audits current manifests and writes reports; never trains. |
| Training entry point | `scripts/ml/train.py` | DEMO data only. Real training is deliberately unsupported until a canonical paired builder and accepted dataset exist. |
| Evaluation/calibration | `scripts/ml/evaluate.py`, `scripts/ml/calibrate.py` | Research utilities; no eligible real dataset and therefore no accepted metrics/calibration. |
| Model registry slots | `artifacts/models/{demo,candidate,production}/` | Demo is pinned; candidate acceptance is blocked; production slot is empty. |
| Configuration | `configs/` | Existing runtime config plus categorized candidate training/evaluation/security/deployment config. |

## Intended data flow

```text
providers -> ingestion -> source validation -> canonical source records
  -> temporal/spatial alignment -> observation-aware target + feature masks
  -> versioned prepared dataset -> chronological split -> train-only normalization
  -> masked training -> validation calibration/model selection -> untouched test
  -> acceptance record -> checksummed registry -> approved inference -> API -> web
```

The repository currently stops before the canonical ERA5/LIS pairing and prepared real dataset. The training and acceptance steps above are prospective; they must not be represented as operationally complete.

## Retained noncanonical code

`ml/research/strikecast` and `ml/training/strikecast_training` contain research model/training code; `ml/research/legacy_api` is compatibility code; `packages/strikecast_core` owns the served runtime. Multiple ConvLSTM implementations exist across these contexts. They are not interchangeable artifacts. They remain in place because tests and research experiments depend on them; do not promote them into serving without an explicit schema, checkpoint, and API compatibility review.

## Known architecture gaps

- No source-derived ERA5/LIS pairing builder creates complete target masks.
- Training CLI only accepts synthetic/demo sources and does not consume real paired datasets.
- Current inference serves synthetic/demo atmospheric features even where an upstream weather adapter may be live; metadata must continue to report demo model status.
- In-memory rate limits do not coordinate across processes/replicas.
- API logs include rounded coordinates and model metadata; privacy review should decide whether location logging is needed.
- No Git metadata is available in this checkout, so commit identity cannot be recorded or verified here.

See [DATA_PIPELINE.md](DATA_PIPELINE.md), [ML_PIPELINE.md](ML_PIPELINE.md), and [ROUND2_RUNBOOK.md](ROUND2_RUNBOOK.md).
