# Deployment status and controls

Current deployment configuration is local/demo only. The API launcher `apps/api/run_api.py` binds `0.0.0.0` and sets `reload=True`; use only for development. Production needs a managed ASGI process, explicit production CORS origins, TLS termination, edge request/time limits, distributed rate limiting, secret injection, read-only model/config mounts, and monitored health checks. HSTS belongs at verified HTTPS termination, not this local HTTP app.

The compose file maps local web/API ports and defaults to DEMO. It is not evidence of hardened deployment. Frontend build arguments such as `VITE_API_BASE_URL` are public and must contain no secrets. `VITE_API_BASE_URL` defaults to HTTP localhost in local compose; production must supply the HTTPS API origin.

Before deployment, run Python and frontend tests/builds, API smoke and security tests, checkpoint integrity validation, leakage audit, dependency scanning, and compose config/build in the target environment. Record environment, image digests, artifact hashes, test output and HTTPS/proxy configuration. Production promotion is blocked while data/model acceptance remains incomplete.
