#!/usr/bin/env bash
set -e
(python3 -m venv .venv; . .venv/bin/activate; pip install -r requirements.txt; python apps/api/run_api.py) &
(cd apps/web && npm install && npm run dev) &
wait
