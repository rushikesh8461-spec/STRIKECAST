# Release checklist

- [ ] Dataset sources, licensing, targets, labels, and provenance reviewed independently.
- [ ] Chronological and spatial held-out evaluation completed on real labeled observations.
- [ ] Candidate model, preprocessing, calibration, and risk policy reviewed and accepted.
- [ ] Security, deployment, and operational monitoring reviewed for intended environment.
- [ ] Run `python scripts/verification/run_all_checks.py`; inspect `artifacts/reports/final_check.json`.
- [ ] Run frontend checks from `apps/web/`: `npm ci; npm run typecheck; npm test; npm run build; npm run test:e2e`.
- [ ] Verify Compose in deployment environment with `docker compose -f infra/compose/docker-compose.yml config` and build/run the stack.
- [ ] Confirm all status labels and user-facing claims match evidence. DEMO_ONLY is not a forecast approval.
