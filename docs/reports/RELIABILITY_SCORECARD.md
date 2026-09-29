# Reliability scorecard

## Evidence levels

| Level | Name | Evidence needed |
|---|---|---|
| 0 | NOT IMPLEMENTED | No usable path |
| 1 | PROTOTYPE | Experimental path exists; reliability not established |
| 2 | DEMO VERIFIED | Deterministic, explicitly labeled demo works |
| 3 | SOFTWARE VERIFIED | Automated tests/integration checks cover software behavior |
| 4 | DATA VALIDATED | Real source/provenance/quality verified |
| 5 | ML VALIDATED | Real chronological train/validation/test evaluation demonstrates forecast skill |
| 6 | OPERATIONALLY VALIDATED | Appropriate operational period, monitored deployment and response validated |

| Subsystem | Highest supported level | Evidence / reason it stops here |
|---|---|---|
| M1 demo data | Level 3 SOFTWARE VERIFIED | deterministic demo + provider contract/fail-closed tests; no operational source data review |
| M1 live atmospheric adapter | Level 1 PROTOTYPE | Open-Meteo adapter and response checks exist; no recorded live provider success/independent QA |
| Real lightning | Level 0 NOT IMPLEMENTED | no verified provider configured; live mode returns unavailable |
| M2 transforms | Level 3 SOFTWARE VERIFIED | leakage, temporal, split, train-only normalization and schema tests; packaged demo too small |
| M3 bundled ConvLSTM | Level 2 DEMO VERIFIED | checksum/schema-verified artifact and deterministic endpoint smoke; synthetic training only |
| M3 real forecast | Level 0 NOT IMPLEMENTED | no accepted labeled data or selected model |
| M4 risk policy | Level 3 SOFTWARE VERIFIED | API returns separate raw/calibrated fields, threshold version/status and covered categories; thresholds provisional |
| Calibration | Level 1 PROTOTYPE | offline candidate fitting utility only; no measured held-out calibration |
| M5 API | Level 3 SOFTWARE VERIFIED | local suite covers contracts, limits, safe errors, headers, CORS, rate limit and fail-closed LIVE |
| M6 UI | Level 3 SOFTWARE VERIFIED | typecheck/build, component tests and Playwright with mocked API/providers |
| External weather products | Level 1 PROTOTYPE | provider integration code; no configured provider success or licensing review |
| Geocoding UI | Level 3 SOFTWARE VERIFIED | bounded response parsing and mocked tests; no service uptime evidence |
| Docker/CI | Level 1 PROTOTYPE | files/workflow exist; neither Docker nor hosted CI executed here |
| Operational monitoring | Level 1 PROTOTYPE | structured request logs only; metrics, traces, alerting and runbook not deployed |

No subsystem is DATA VALIDATED, ML VALIDATED, or OPERATIONALLY VALIDATED. Software evidence must not be treated as forecast evidence.
