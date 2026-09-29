# Archived StrikeCast archive and workspace integration audit

> Historical archive comparison. Several runtime, API security, and provider statements below describe the workspace before the final hardening pass and are superseded by `../FINAL_VERIFICATION_REPORT.md` and `../ARCHITECTURE_DECISION_RECORD.md`. Retained for archive selection traceability; do not use as current runtime guidance.

## Scope and method

Reviewed the current `StrikeCast/` workspace and all three supplied archives. The integrated archive has 146 entries, M5 has 39, and M3 has 37. Source and contract files were inspected in each archive family and compared with the current workspace inventory. The archives are treated as untrusted source material. The command-center archive is the checked-out workspace itself; no fourth zip was supplied.

## Selection

| Component | Archive/workspace | Implementation reviewed | Assessment | Selected |
|---|---|---|---|---|
| M1 ingestion | Current workspace; integrated archive | Open-Meteo atmospheric point adapter and separate multimodal demo ingestion with validation/provenance | Point API has deterministic synthetic fallback; the richer M1 package has schema, source and quality modules. Neither provides verified lightning observations in this environment. | Keep workspace `m1-data/` for the currently wired API and `strikecast/src/ingestion/` for the reproducible multimodal dataset pipeline. These serve distinct ingestion interfaces; do not represent demo data as live. |
| M2 features | Current workspace; integrated archive | Lightweight point feature adapter and 19-channel causal spatial/temporal feature pipeline | Full pipeline documents channel order, chronological splits, train-only normalization and leakage tests. Demo has only 12 time steps and zero validation/test windows. | Keep both as separate adapters only until the point API is replaced by the multimodal contract; do not claim they are interchangeable. |
| M3 model | Integrated, M3 archives and workspace | ConvLSTM, persistence, classical ML, fusion, training/checkpoint/inference modules; separate small command-center ConvLSTM artifact | M3 archives share the core. Integrated adds M2 bridge and preprocessing. Command-center weights were trained on synthetic patterns and are demo-only. | Keep `strikecast/src/models` and `strikecast/src/training` as the research/training source; keep `m3-model` only as the command-center demo inference adapter. No candidate has defensible real-data skill. |
| M4 evaluation/risk | Workspace | Probability transform and risk band thresholds | Fixed transform and thresholds have no calibration dataset or validation evidence. Evaluation helper exists but no benchmark report. | Keep `m4-risk/risk_engine.py` as provisional demo logic; status explicitly provisional. No production calibration selected. |
| M5 API | M5 archive and workspace | Archive has service/model-loader/schema layers, mock and placeholder real model modes, structured errors and MLflow hook. Workspace API directly connects M1–M4 and supports lightning route. | M5 archive's real predictor is a placeholder; its mock predictor emits a location hash score. Workspace API is functional but lacked input grid bounds and leaked raw exception details. | Keep `m5-backend/app` as the one served API because it is the only currently wired M1→M4 path; apply request validation and generic client errors. M5 archive remains reference material, not a second served application. |
| M6 geospatial UI | Workspace | React, MapLibre, risk overlays, weather products, lightning adapter and 3D scene | Existing frontend is the supplied command center and calls the central API; no browser-created model prediction path identified. | Preserve `m6-frontend/` without redesign. |
| Security | M5 archive and workspace | M5 schemas use bounded coordinates/horizon and clean global errors; workspace has coordinate bounds and explicit CORS origins | Workspace previously returned exception strings and accepted unbounded, non-rectangular grids. No rate limiter, request ID, response security headers or body-size middleware is present. | Apply stricter request grid validation and generic API errors. Remaining controls are recorded as gaps, not claimed complete. |
| Testing | All sources | M5 API tests, M3 architecture/training tests, integrated preprocessing/ingestion/features tests, workspace API tests | Test suites overlap and some imports depend on working directory. Initial root pytest collection failed on `m5-backend/tests/test_api.py` (`No module named app`). | Preserve upstream suites; establish import path and execute separately, then record actual results. |
| Deployment | M5 archive and workspace | Archive Docker/compose/CI; workspace Windows launch scripts and Vite frontend | Workspace run script starts its API and frontend. M5 archive targets a different placeholder API and is not the entry point. | Keep workspace scripts as local demo launch path; retain M5 deployment files for review only until unified/container verification is complete. |

## Canonical flow and current boundary

```text
M1 real Open-Meteo when reachable OR explicitly labeled synthetic fallback
  → M2 point normalization/features
  → M3 bundled synthetic-demo ConvLSTM
  → M4 unvalidated probability transform and provisional thresholds
  → M5 FastAPI (`m5-backend/app`)
  → M6 React/MapLibre command center
```

The distinct research pipeline is `strikecast/src/ingestion → preprocessing/features → models/training → evaluation`. It is not silently substituted into the point API: the research tensor is `[batch,time,lat,lon,channels]` with 19 channels, while the wired point model uses `[time,3,3,8]`. A proper bridge needs a shared trained artifact, preprocessing metadata and target contract; no such compatible artifact is available. The M5 archive's placeholder API is not served, preventing a second competing prediction path.

## Current limitations

- No verified lightning labels or atmospheric training dataset was supplied. Demo artifacts and synthetic training data are not observational evidence.
- The bundled processed split has 3 train windows and 0 validation and test windows. It cannot establish model selection, calibration or accuracy.
- Open-Meteo fallback hides upstream failure behind `data_source`; UI/API status needs to remain clearly demo/offline when fallback is used.
- API does not yet enforce request rate limits, maximum body bytes, request IDs or security headers. Production deployment and Docker/E2E verification are incomplete.
- Root test collection initially fails because the M5 API package is not on `sys.path` when tests run from the repository root.

## Archive inventory summary

- `strikecast_integrated.zip`: M1 source/validation/storage, M2 feature and preprocessing pipeline, M3 model/training/inference, demo and processed arrays, contracts/tests.
- `strikecast_m3.zip`: M3 model alternatives, training/checkpoint/inference, configs and focused tests; overlaps the integrated M3 core.
- `StrikeCast-M5.zip`: standalone M5 API/service/model-loader/risk schemas, MLflow hooks, Docker, CI and API tests; its real model class is not implemented beyond checkpoint loading.
- Existing workspace: command-center UI and adapters, demo model weights, integrated research package and an additional wired API. Its runtime choices are documented above.
