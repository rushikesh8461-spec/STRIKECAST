# LIVE production gate

Current value: `LIVE_FORECAST_STATUS = BLOCKED`. The API returns 503 in `LIVE` and `VALIDATION` modes until an accepted model path is integrated; do not change that gate based on code presence or demo tests.

Required evidence before LIVE forecast serving:

- [ ] Real atmospheric provider/use case verified, including terms, rate limits, coverage, cadence, units and failure handling
- [ ] Licensed, independently verified lightning observations and target labels
- [ ] Target definition and operational forecast horizon/spatial support approved
- [ ] Adequate chronological train, validation and untouched test periods/event counts
- [ ] Leakage, missingness, physical range, source provenance and quality audits independently reviewed
- [ ] Normalization/preprocessing schema fitted on training only and version-matched
- [ ] Persistence and appropriate statistical baselines benchmarked on identical splits
- [ ] Candidate models compared using rare-event, probability, spatial and lead-time metrics
- [ ] Model acceptance criteria met on untouched test data with uncertainty analysis
- [ ] Calibration fitted only on validation and evaluated on untouched test data
- [ ] Risk and alert policies validated with operational stakeholders and false-alarm tradeoffs
- [ ] Checkpoint architecture/schema/preprocessing/dataset/version/checksum metadata validated
- [ ] No arbitrary model path loading; registry/rollback process reviewed
- [ ] Security, API, frontend, provider timeout/rate-limit and failure tests passed
- [ ] Deployment, metrics, traces, alerting, provider health, runbooks and rollback tested
- [ ] Docker image and hosted CI verified in target environment

Current gate results: Dataset `NOT_READY`; model `DEMO_ONLY`; calibration `NOT_VALIDATED`; provider `UNAVAILABLE` for operational lightning; forecast skill `NOT_YET_PROVABLE`.
