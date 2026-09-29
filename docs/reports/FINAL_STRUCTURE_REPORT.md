# Final structure report

Date: 2026-09-28. The migration recovery completed without changing the architecture. The full post-cleanup file and directory tree is in [`artifacts/reports/repository_tree.txt`](../../artifacts/reports/repository_tree.txt).

## Canonical layout

```text
StrikeCast/
├── apps/
│   ├── api/strikecast_api/main.py
│   └── web/
├── packages/strikecast_core/
│   ├── data/
│   ├── evaluation/
│   ├── features/
│   ├── models/
│   ├── risk/
│   ├── schemas/
│   └── security/
├── ml/
│   ├── training/
│   ├── experiments/
│   └── research/
├── data/
├── artifacts/
├── configs/
├── scripts/
├── tests/
├── docs/
├── infra/
└── .github/
```

Dependencies flow from frontend to API to `packages/strikecast_core`; ML code uses core; tests cover the relevant layers. Core does not import apps. The research pipeline and legacy compatibility API remain research-only.

## Current evidence

- Old M1–M6 top-level directories: absent.
- Canonical API, core, frontend, model, and risk locations are present.
- The structure validator confirms one served FastAPI app, one runtime model definition, one risk implementation, one verified checkpoint loader, and one API schema source.
- No production model checkpoint is present. The demo checkpoint remains at `artifacts/models/demo/strikecast_convlstm_demo.pt` with SHA-256 `63150034a809d39a4f60f0003f1de7786d7e9a51457c114adc02a25123ce8cfb`.
- Generated caches, `node_modules`, frontend `dist`, and Playwright results were removed after testing.
- Structure and configuration validators passed after cleanup.

The verification record is in [FINAL_VERIFICATION_REPORT.md](FINAL_VERIFICATION_REPORT.md), [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md), and the path-sanitized machine-readable [`final_check.json`](../../artifacts/reports/final_check.json).
