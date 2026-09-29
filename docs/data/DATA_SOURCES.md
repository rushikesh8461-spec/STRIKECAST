# Data sources and provenance

## Current serving configuration

- Atmospheric: deterministic synthetic DEMO points; the Open-Meteo HTTPS adapter is available for explicit provider calls but not activated by the serving runtime. It validates response MIME, byte limit, fields, timestamps and physical bounds. Provider terms, access and observation licensing must be reviewed before operational use.
- Lightning: deterministic StrikeCast presentation simulation by default. It is marked `demo`; it is not an observation feed.
- Radar/satellite products: no provider configured by default; frontend shows unavailable unless an allowed tile provider is configured.
- Research demo arrays: mock NWP/radar/satellite/lightning files under `data/demo/research_multimodal`; all are explicitly mock.

## Real dataset intake

Raw ERA5 and ISS-LIS files were supplied and copied intact under `data/raw/`; see [`DATASET_INVENTORY.md`](../../artifacts/reports/DATASET_INVENTORY.md). The uploaded files do not provide valid one-hour paired labels or suitable chronological splits. Their acquisition records, exact LIS V3.0 product documentation, and license/terms review are incomplete. Any candidate dataset must document provider/source, license, download time, version, SHA-256, coverage, cadence/resolution, variables/units, target labeling procedure, missingness and quality report. Keep licensed/private raw data out of version control. Use the manifest and tensor rules in `DATASET_CONTRACT.md`; validation is not independent provenance review or scientific acceptance.
