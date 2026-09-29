# StrikeCast web app

This is the React/MapLibre client. `src/app/main.tsx` mounts the application, and `src/services/apiClient.ts` centralizes backend requests. Presentation code does not calculate model predictions or risk.

From this directory, run `npm ci`, copy `.env.example` to `.env`, then run `npm run dev`. Set `VITE_API_BASE_URL` to the API base. Browser-visible `VITE_*` values must not contain private credentials.

Run `npm run typecheck`, `npm test`, `npm run build`, and `npm run test:e2e`. E2E stubs backend, geocoder, and map tiles. Weather layers report unavailable until configured; DEMO lightning and risk presentation remain explicitly labeled.

See the [root README](../../README.md), [API contract](../../docs/api/API.md), and [verification report](../../docs/reports/FINAL_VERIFICATION_REPORT.md).
