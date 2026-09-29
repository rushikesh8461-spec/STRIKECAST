# StrikeCast

StrikeCast is a research and demonstration system for point-based atmospheric and lightning-risk exploration. It combines a React/MapLibre command center with a single FastAPI service, shared runtime core, and separate research/training packages.

**Scientific status:** the bundled ConvLSTM was trained on synthetic data. The demo dataset has too few windows for independent validation/test partitions. There are no accepted observational lightning labels, held-out evaluations, or measured calibration results. StrikeCast cannot claim forecast skill or production readiness.

## Repository layout

- `apps/api/strikecast_api/`: only served FastAPI application; `apps/api/run_api.py` launches it.
- `apps/web/`: React/MapLibre UI and API client.
- `packages/strikecast_core/`: shared serving contracts for data, features, inference, risk and evaluation.
- `ml/training/`: experimental trainer package; `ml/experiments/`: experiment configurations.
- `ml/research/strikecast/`: separate multimodal data and modeling research pipeline. It is not connected to serving.
- `data/`, `artifacts/`, `scripts/`, `tests/`, `docs/`, `infra/`: data, model/check outputs, tools, verification, documentation and deployment.

See [the architecture](docs/architecture/ARCHITECTURE.md), [migration map](docs/architecture/MIGRATION_MAP.md), and [final structure report](docs/reports/FINAL_STRUCTURE_REPORT.md) for ownership and move details.

## Runtime modes

- `DEMO` (default): deterministic synthetic atmospheric data and the pinned demo checkpoint. Responses identify `DEMO` and `DEMO_ONLY` status.
- `VALIDATION`: public predict/risk endpoints fail with 503; use offline dataset and evaluation tools.
- `LIVE`: fails closed with 503 until an accepted production model and real-data inference adapter exist.

The optional Open-Meteo adapter is bounded but is not used by DEMO serving. Lightning defaults to a labeled presentation simulation. Live lightning requires an explicit HTTPS host allowlist and provider configuration.

## Setup

Backend (Python 3.11):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python apps/api/run_api.py
```

Frontend (Node 22), in another terminal:

```powershell
cd apps/web
npm ci
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`. Set `VITE_API_BASE_URL` in `apps/web/.env`. Never put private credentials in `VITE_*` variables.

Cross-platform launchers are `run-strikecast.bat`, `run-all.ps1`, and `run-all.sh`. On Windows, `install-windows.bat` installs dependencies.

## API and scientific limitations

The service provides `GET /health`, `GET /metadata`, `POST /predict`, `POST /risk`, and `GET /lightning`. `/risk` reports a raw score, null calibrated probability, `NOT_VALIDATED` calibration status, provisional policy version, and forecast horizon. Thresholds are policy cutoffs, not calibrated values. Do not use demo outputs for safety decisions; follow official warnings.

## Data and model tools

- Validate a provenance-bearing dataset: `python scripts/data/validate.py <dataset-dir>`.
- Train a synthetic demo artifact: `python scripts/ml/train.py --mode DEMO --data synthetic`.
- Evaluate supplied held-out labels/probabilities: `python scripts/ml/evaluate.py --data <predictions.npz>` (requires `y_true` and `probabilities`; review provenance and split independence separately).
- Calibrate a candidate only: `python scripts/ml/calibrate.py --validation <validation.npz> --test <untouched-test.npz>`.
- Validate the bundled demo checkpoint: `python scripts/ml/validate_checkpoint.py`.

No real-data training, production model registration, or promotion path is available. Dataset requirements are in [the dataset contract](docs/data/DATASET_CONTRACT.md); source and licensing notes are in [data sources](docs/data/DATA_SOURCES.md).

## Verification and deployment

Run `python scripts/verification/run_all_checks.py`. It records command output in `artifacts/reports/final_check.json`. See [verification report](docs/reports/VERIFICATION_REPORT.md) and [final verification report](docs/reports/FINAL_VERIFICATION_REPORT.md) for results and limitations.

Compose configuration and startup:

```powershell
docker compose -f infra/compose/docker-compose.yml config
docker compose -f infra/compose/docker-compose.yml up --build
```

No atmospheric/lightning provider is configured for serving, no production artifact exists, demo forecast skill is unproven, risk thresholds are provisional, and calibration is not validated.
