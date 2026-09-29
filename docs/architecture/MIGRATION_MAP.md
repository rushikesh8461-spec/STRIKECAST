# Monorepo migration map

The physical consolidation completed on 2026-09-27. The M1–M6 names below are historical source locations, not active directories. The migration recovery run on 2026-09-28 verified the current layout and freezes the boundaries described in [ARCHITECTURE.md](ARCHITECTURE.md).

| Historical location | Current location | Runtime status |
|---|---|---|
| `m1-data/` | `packages/strikecast_core/data/` | Served atmospheric and lightning adapters |
| `m2-features/` | `packages/strikecast_core/features/` | Served point feature construction |
| `m3-model/` | `packages/strikecast_core/models/` | Single inference adapter and runtime model |
| `m3-model/artifacts/demo/strikecast_convlstm_demo.pt` | `artifacts/models/demo/strikecast_convlstm_demo.pt` | Synthetic/demo artifact; DEMO_ONLY |
| `m4-risk/` | `packages/strikecast_core/risk/` and `packages/strikecast_core/evaluation/` | Provisional risk policy and separate evaluation helpers |
| `m5-backend/` | `apps/api/strikecast_api/` | Sole served API; shared contracts now live in `packages/strikecast_core/schemas/` |
| `m6-frontend/` | `apps/web/` | Canonical web command center |
| `strikecast/src/` | `ml/research/strikecast/src/` | Independent multimodal research pipeline |
| `strikecast/src/training/` | `ml/training/strikecast_training/` | Research/training utilities |
| `strikecast/api/`, `mlops/`, `scripts/` | `ml/research/legacy_api/` | Compatibility research code; not served |
| `strikecast/tests/` | `tests/research/strikecast/` | Research regression tests |
| `strikecast/data/sample_demo/` | `data/demo/research_multimodal/` | Mock/demo inputs |
| `strikecast/config/` | `configs/research/` | Research reference configuration |
| `strikecast/configs/` | `ml/experiments/configs/` | Experiment configurations |
| root operator scripts | `scripts/{data,development,ml,verification}/` | Grouped maintenance and verification commands |
| root deployment files | `infra/docker/`, `infra/compose/` | Current API image and Compose definitions |

No old M1–M6 top-level directories remain. The source audit found no active references to those old paths outside this migration map and historical migration reports. No verified real labeled dataset, production checkpoint, calibration result, or scientific performance claim was introduced.
