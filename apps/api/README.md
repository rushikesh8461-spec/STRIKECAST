# API application

`strikecast_api.main:app` is the only served API entrypoint; launch it from the repository root with `python apps/api/run_api.py`. It validates requests and orchestrates the shared `packages/strikecast_core` modules.

Install root dependencies with `python -m pip install -r requirements.txt`. Runtime settings come from the process environment and root `.env`. YAML files under `configs/` are reference snapshots, not runtime input.

Routes: `GET /health`, `GET /metadata`, `POST /predict`, `POST /risk`, and `GET /lightning`. DEMO supports software demonstration only. VALIDATION/LIVE predict and risk calls fail closed until accepted real data and a compatible validated model path exist.
