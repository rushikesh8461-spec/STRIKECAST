# Model card: served demonstration model

## Status and intended use

Status: `DEMO_ONLY`. The bundled ConvLSTM demonstrates the software/API contract only. It is not an evaluated probability of lightning at a defined location, radius, or forecast window and must not be used for warnings or operational decisions.

## Artifact and known lineage

- Architecture: compact ConvLSTM at `packages/strikecast_core/models/runtime_convlstm.py`.
- Artifact: `artifacts/models/demo/strikecast_convlstm_demo.pt`.
- SHA-256: `63150034a809d39a4f60f0003f1de7786d7e9a51457c114adc02a25123ce8cfb`.
- Input: six steps, 3×3 shape device, eight point-derived channels; synthetic/demo-trained.
- Dataset, target, training configuration, split, feature schema lineage and observed-label evaluation are not sufficient for candidate acceptance. The sidecar manifest identifies the synthetic/demo dataset only; missing real provenance is not inferred.
- Calibration: `NOT_VALIDATED`; raw probabilities only. Risk thresholds are provisional.

No accuracy, rare-event metric, calibration, resource, or comparative-performance figure is claimed. The acceptance record in `artifacts/models/candidate/acceptance.json` remains `BLOCKED`; no candidate or production artifact is registered. Dataset validation, held-out evaluation, calibration, and LIVE serving remain blocked until real licensed observations and lightning labels pass review.
