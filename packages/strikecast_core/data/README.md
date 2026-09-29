# M1 â€” served data adapters

`atmospheric.py` and `lightning.py` are the shared atmospheric and lightning adapters used by the canonical FastAPI application in `apps/api/strikecast_api/main.py`.

- DEMO atmospheric input is deterministic synthetic data and is explicitly labeled.
- The optional Open-Meteo adapter is a bounded live-provider utility; serving does not silently fall back to it or synthetic data on provider failure.
- Lightning simulation is deterministic and labeled DEMO. LIVE lightning requires an explicitly configured HTTPS host allowlist; otherwise the API reports unavailable.
- `ml/research/strikecast/src/ingestion/` is a separate provenance-aware research dataset pipeline and does not replace the served adapters.

See [provider behavior](../../../docs/operations/EXTERNAL_PROVIDERS.md), [demo status](../../../docs/hackathon/DEMO_MODE.md), and the [final verification report](../../../docs/reports/FINAL_VERIFICATION_REPORT.md).
