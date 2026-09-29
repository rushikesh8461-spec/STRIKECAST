# Feasibility matrix

**Reliability vocabulary:** Level 0 NOT IMPLEMENTED; Level 1 PROTOTYPE; Level 2 DEMO VERIFIED; Level 3 SOFTWARE VERIFIED; Level 4 DATA VALIDATED; Level 5 ML VALIDATED; Level 6 OPERATIONALLY VALIDATED. A level indicates evidence reached, not product maturity. No StrikeCast forecasting subsystem currently exceeds Level 3.

“Runnable” means the software path can execute in the local project. Provider availability, scientific validity, and production eligibility are separate.

| Component | Implemented | Runnable | Tested | Real Data Required | Scientifically Validated | Production Eligible | Status |
|---|---|---|---|---|---|---|---|
| M1 module | Yes | Yes | Yes, contract tests | For operational observations: yes | No | No | Level 3 software path; demo input only |
| M2 module | Yes | Yes | Yes, leakage/split/normalization tests | For operational features: yes | No | No | Level 3 transforms; demo windows inadequate |
| M3 module | Yes | Yes | Yes, shape/checkpoint tests | For forecast claims: labeled real data | No | No | Level 2 demo artifact; model selection BLOCKED_BY_DATA |
| M4 module | Yes | Yes | Yes, policy/API tests | For validated policy: yes | No | No | Level 3 software policy, provisional thresholds |
| M5 module | Yes | Yes | Yes, API/security suite | Not to execute demo; yes for LIVE | No | Demo deployment only | Level 3 API software; LIVE blocked |
| M6 module | Yes | Yes | Yes, units/build/E2E mocks | External services for live products | No | Demo deployment only | Level 3 frontend software |
| Atmospheric ingestion | Yes | Yes | Yes, deterministic and provider failure tests | Yes for real observations | No independent source QA | No | DEMO verified; Open-Meteo adapter technically feasible, serving does not use it |
| Lightning ingestion | Yes | Yes | Yes, validation and mode tests | Yes | No verified operational provider | No | Demo simulation; LIVE unconfigured returns unavailable |
| Weather layers | Yes | Yes | E2E unavailable-state only | Provider tiles/API | No | No | Level 3 unavailable behavior; provider absent |
| Satellite | Adapter/config exists | Only with provider | No provider success run | Yes | No | No | UNAVAILABLE by default |
| Radar | RainViewer metadata adapter | Only with provider | E2E unconfigured path | Yes | No | No | UNAVAILABLE by default; license/coverage review needed |
| Geocoding | Yes (Nominatim) | Yes | Unit/E2E mocked | External API | Not applicable to forecast skill | Limited demo use | Level 3 client behavior; no provider availability/SLA proof |
| Prediction | Yes | DEMO executes; LIVE/VALIDATION 503 | API and E2E mocked | Labeled data for real predictions | No | Demo only | Demo-only score, not an evaluated event probability |
| Risk | Yes | Yes | API and unit coverage | Operational data for policy validation | No | No | Raw probability to provisional category; not a warning product |
| Calibration | Candidate offline utility only | With validation labels | No empirical evidence | Validation labels required | No | No | NOT_VALIDATED; API returns null calibrated probability |
| Search | Yes | Yes | Unit/E2E mocked | External geocoder | Not applicable | Limited demo use | Level 3 frontend behavior |
| Map | Yes | Yes | E2E mocked tiles | External tiles for basemap | Not applicable | Limited | Level 3 UI behavior; point radius is illustrative only |
| Alerts | Provisional static copy | Yes | API/E2E mocked | Operational policy and labels | No | No | Demo text, not official alerts |
| DEMO mode | Yes | Yes | Determinism smoke test | No | Not applicable | Demo only | Level 2/3 demo and software verified |
| LIVE mode | Fail-closed gate | Returns 503 | API smoke/test | Accepted data/model required | No | No | BLOCKED as intended |
| Training | Research trainer + demo CLI | DEMO only | Existing training tests | Real data for meaningful training | No | No | Research/demo only; no accepted real-data training path |
| Evaluation | NPZ metrics utility | Yes for supplied arrays | Metric primitives tested | Held-out labeled test data | No repository benchmark | No | NOT PROVEN; selection BLOCKED_BY_DATA |
| Docker | Config/images | Unknown locally | Not run | No | Not applicable | Not verified | Docker CLI unavailable |
| CI | Workflow configured | Hosted only | Not run hosted | No | Not applicable | Not verified | Configuration present; run unavailable |
| Security | API and provider controls | Yes | Security tests; npm audit | Not applicable | No external review | No | Partial software controls; distributed controls/review absent |
| Observability | Structured request logs | Yes | Logging checked indirectly | Not applicable | No | No | Basic request logging; no metrics/tracing/monitoring |

## Feasibility by capability

- **Lightning forecasting:** technically feasible as a research task; ingestion/model interfaces are partial; needs licensed observations, explicit event/radius/time target, substantial labels, chronological splits, baselines and evaluation. No credentials are currently configured. DEMO exists; production forecast is not justified.
- **Atmospheric data:** Open-Meteo point observations can be fetched without credentials through the adapter, subject to provider terms/rate policies. It is not wired into serving. This does not provide verified lightning labels.
- **Radar/satellite:** technically feasible through an approved tile/data provider. URLs are unset; provider license, coverage, resolution and availability remain unverified.
- **Model evaluation/calibration:** utilities are feasible with externally supplied, provenance-reviewed labels/predictions. Current demo data cannot support it.

See `RELIABILITY_SCORECARD.md` and `PRODUCTION_GATE.md` for subsystem disposition and release requirements.
