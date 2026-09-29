# Architecture

The repository is a frozen monorepo. Serving follows one direction: the web app calls the API, and the API uses the shared core. ML training and experiments may depend on core interfaces; core never imports applications.

```text
StrikeCast/
├── apps/
│   ├── api/                 canonical FastAPI service
│   └── web/                 React and MapLibre command center
├── packages/
│   └── strikecast_core/     data, features, inference, risk, schemas, security
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

Dependency direction:

```text
Frontend → API → packages/strikecast_core
ML       → packages/strikecast_core
Tests    → relevant layers
```

The runtime API, schema source, checkpoint loader, inference adapter, and risk engine each have one canonical implementation. Research and compatibility code under `ml/research/` remains separate and is not imported by the served API.

`artifacts/models/demo/strikecast_convlstm_demo.pt` is synthetic/demo-trained and marked `DEMO_ONLY`. The dataset is not validated, held-out evaluation is not established, calibration is not validated, risk thresholds remain provisional, and LIVE forecasts are blocked. Demo output is not evidence of forecast skill.

See [migration map](MIGRATION_MAP.md), [final structure report](../reports/FINAL_STRUCTURE_REPORT.md), and [verification report](../reports/VERIFICATION_REPORT.md).
