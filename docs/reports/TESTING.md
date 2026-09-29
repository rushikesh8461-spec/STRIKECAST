# Testing

Run all local checks with `python scripts/verification/run_all_checks.py`; see `VERIFICATION_REPORT.md` for the last recorded results. Python tests include data contracts, feature leakage/split handling, model loading/training primitives, risk policy, API behavior and security cases. Frontend tests cover runtime labels, API error handling, geocoding and browser UI behavior.

Playwright currently mocks the API, geocoder and map tile responses. It verifies frontend behavior and not a live API/browser deployment. Docker and hosted CI must be run in an environment that provides them.
