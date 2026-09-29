# Deployment

## Local processes

Use `install-windows.bat` and `run-strikecast.bat`, or install Python dependencies from root `requirements.txt`, launch `python apps/api/run_api.py`, then start the Vite app from `apps/web` with `npm ci && npm run dev`. Set `CORS_ORIGINS` to exact trusted frontend origins and `VITE_API_BASE_URL` to the API base. Local demo mode is the default.

## Docker Compose

At repository root run `docker compose -f infra/compose/docker-compose.yml config` then `docker compose -f infra/compose/docker-compose.yml up --build`. Compose builds the canonical API and static frontend. No secrets are provided by Compose. Set public frontend build-time URLs only to approved endpoints; private keys must remain server-side.

The API image runs as UID 10001 and defines a healthcheck. The frontend image uses nginx and response security headers. Docker is not installed in the current verification environment, so these images and the Compose runtime remain untested.

## LIVE restrictions

`STRIKECAST_MODE=LIVE` intentionally returns 503 for prediction and risk. Do not enable live traffic until dataset, model, calibration, risk policy, provider, security and release gates are independently satisfied. The current model status is DEMO_ONLY.
