# Real-data quality report

Run date: 2026-09-28. The new historical source folder was ingested read-only. The canonical raw manifest has 1,134 file paths: 1,131 LIS paths and 3 ERA5 archives. Hash deduplication identifies 1,128 unique readable LIS granules, one exact duplicate path, one zero-byte raw representative, and one unreadable HDF5 file. The external source manifest records all 1,550 incoming LIS paths, including 59 zero-byte files and 420 repeated-content paths. An additional project-root mirror of the 2025 ERA5 ZIP was verified by SHA-256. Detailed checksums and metadata: [`DATASET_INVENTORY.md`](DATASET_INVENTORY.md), [`dataset_inventory.json`](../../data/database/manifests/dataset_inventory.json), and [`historical_lis_ingestion.json`](../../data/database/manifests/historical_lis_ingestion.json).

## Checks executed

- SHA-256 generated for every supplied archive and NetCDF file; the repeated 08:07:40 LIS upload is byte-identical.
- All three ZIP central directories passed `zipfile.testzip()` CRC validation; each contains one member named `data.grib`.
- ecCodes decoded all 121,152 GRIB messages and metadata. ERA5 single-level and pressure-level date/coordinate/field counts are consistent with their documented hourly regional grids; the 2025 archive has 118,800 messages across 275 days.
- In the original November batch, NetCDF-4 opened all eight named files; seven are unique. The historical collection audit and its two schema shapes, empty-file set, and one HDF read failure are recorded separately below and in the machine manifests.
- Historical NetCDF audit opened 1,128 unique non-empty granules. Of these, 1,118 have 147 variables and event/flash tables; 10 have 60 variables and zero event/flash summary counts with those arrays omitted. Fifty-nine incoming file paths are zero-byte; one 12,699-byte file has an HDF read error. None of these were converted into labels.
- Coordinate coverage was intersected against the StrikeCast/ERA5 domain using LIS `viewtime_lat/lon`; event/flash centroids were checked using their own coordinates. Per-granule UTC intervals and metadata for all readable granules are in [`ERA5_REQUIRED_COVERAGE.md`](ERA5_REQUIRED_COVERAGE.md) and its JSON manifest.

## Findings and gate status

| Check | Result | Detail |
|---|---|---|
| File integrity | PASS | ZIP CRC and successful NetCDF/ecCodes reads; original file hashes recorded. |
| ERA5 range/grid structure | PASS, metadata scope | 2023 single/pressure files each cover 24 hourly valid times on the regional grid. Complete value-range/physical plausibility audit is not yet recorded. |
| LIS provenance/version/license | BLOCKED | Filenames/global attrs do not provide acquisition manifest, DOI/license, or confirmed V3.0 product dictionary. |
| LIS quality flags | PARTIAL | Flag values are inventoried. The common-area view-time rows all carry warning value 2; threshold/filter policy needs version-matched review. |
| Common time | PARTIAL | LIS orbit starts span 2023-07-05 through 2023-11-16, but both ERA5 products are supplied together only on 2023-11-16. LIS is sparse orbital sampling. The 2025 ERA5 archive has no LIS overlap. |
| Common space | PARTIAL | 177 of 1,128 readable unique granules have view-time or event/flash coordinates inside 8–20 N, 72–82 E across 76 observation dates. Orbit 111326 is the only domain-intersecting pass on the currently ERA5-covered date. |
| Valid negative labels | BLOCKED | Per-cell view-time union is at most 111 seconds (median 104 seconds) versus 3,600 seconds required; a file's zero in-rectangle flash count is not a negative label. |
| Sample count | BLOCKED | 0 unique valid paired samples for the configured one-step hourly target; 525 candidate cell labels remain unknown in the only intersecting pass. |
| 10,000 target | FAIL / unsupported | Available overlap is far below target; no oversampling or synthetic samples were created. |

No training, calibration, held-out evaluation, or model selection was run because target validity and temporal coverage fail before those steps. No model metrics are available.

The required valid-sample count remains **0 of 10,000**. Exact additional co-located coverage needs are recorded in [`DATA_REQUIREMENT_FOR_10K.md`](DATA_REQUIREMENT_FOR_10K.md); a calendar-duration estimate is not supported by the sparse current sample.
