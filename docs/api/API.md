# API contract

Canonical served application: `apps/api/strikecast_api/main.py`, launched from the repository root with `python apps/api/run_api.py` on port 8000.

Endpoints: `GET /health`, `GET /metadata`, `POST /predict`, `POST /risk`, `GET /lightning?latitude=...&longitude=...`.

Prediction request:

```json
{"latitude": 12.9716, "longitude": 77.5946, "timestamp": "2026-09-26T14:00:00Z", "horizon_minutes": 60, "grid": null}
```

Coordinates are bounded to WGS84; horizon is 5–360 minutes; supplied timestamps must be ISO-8601 with timezone; optional grid must be rectangular, finite and at most 65,536 values. Model path and URL fields are forbidden. Body limit is 1 MiB.

`/predict` returns model score/probability/confidence, model/data status and atmospheric features. In DEMO, data status is always DEMO and the output is repeatable for an identical location/request. The API does not use historical timestamps to query Open-Meteo. Grid is validated and echoed as shape but is not consumed by the point model.

`/risk` adds raw probability, `calibrated_probability: null`, `calibration_status: NOT_VALIDATED`, provisional policy version, risk level and horizon. Thresholds are policy cutoffs; no calibration is claimed.

With `STRIKECAST_MODE=LIVE` or `VALIDATION`, `/predict` and `/risk` return 503 until a validated compatible model and corresponding inference provider have been accepted. There is no automatic demo fallback.
