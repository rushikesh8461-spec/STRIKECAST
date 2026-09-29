# External provider inventory

| Category | Provider/endpoint in code | Credentials | Rate/license/coverage evidence | Resolution | Failure behavior | Runtime status |
|---|---|---|---|---|---|---|
| Atmospheric | Open-Meteo `https://api.open-meteo.com/v1/forecast` in `packages/strikecast_core/data/atmospheric.py` | None in adapter | Not independently reviewed here; provider terms/limits must be checked before use | Point hourly fields; request covers past/forecast periods | timeout, no redirects, JSON and 1 MB bounds; raises; serving DEMO does not call it | Adapter only; not operationally activated |
| Lightning | User-supplied `LIGHTNING_FEED_URL` in `packages/strikecast_core/data/lightning.py` | Optional bearer token from server environment | No provider/license/source configured; exact host allowlist required | Provider dependent | redirects blocked, timeout, JSON, 1 MB, max 500 deduped validated strikes; unavailable response when missing/failing | UNAVAILABLE unless explicitly configured; default presentation simulation is DEMO |
| Radar | User-supplied RainViewer API metadata URL in frontend | No key currently | No service/license/SLA review or successful run | Provider metadata + raster tiles; exact operational resolution unknown | Invalid/blocked metadata maps to UNAVAILABLE | No URL configured by default |
| Satellite | User-supplied raster tile template | Provider dependent | No provider configured/license reviewed | Provider dependent | No URL => UNAVAILABLE | UNAVAILABLE |
| Geocoding | Nominatim search/reverse endpoints | No key in current demo client | Public-service policy/rate obligations and availability must be reviewed; no SLA verified | Place results, not forecast data | timeout, redirect disabled, JSON/1 MB limits, coordinate shape checks; UI error | External optional functionality, not forecast validation |
| Basemap | OpenStreetMap tile URL template | No key | Tile usage policy must be followed; no availability/SLA verification | XYZ raster tiles | Map errors; UI retains unavailable map behavior | Browser E2E currently mocks tiles |

No provider is called “operationally verified” based on its URL being present in source. Credentials belong on servers; no private credentials should be placed in `VITE_*` variables.
