# Data required to reach 10,000 valid samples

Status date: 2026-09-28

## Current audited quantity

The new source folder `NEW DATA/` contains 1,550 LIS `.nc` paths from two overlapping collections (362 and 1,188 files). SHA-256 found 1,130 distinct contents including one empty-file hash, 420 repeated-content paths, 59 zero-byte paths, and 7 contents already present in the earlier raw batch. There are 1,129 distinct non-empty contents; one is an unreadable 12,699-byte HDF5 file and 1,128 unique NetCDF/HDF5 granules were readable and inventoried. The filename/metadata period spans 2023-07-05 through 2023-11-16; LIS coverage is orbital and sparse. No additional ERA5 files were supplied. ERA5 single-level and pressure-level data remain available together only for 2023-11-16; the 2025 single-level archive is unrelated to the LIS periods.

After checking actual LIS view-time coordinates against the ERA5 rectangle, just one granule intersects it: orbit 111326 on 2023-11-16, with 991 view-time rows across 345 distinct 0.5-degree centers during approximately 11:38:53–11:44:37 UTC. The union of view-time intervals per observed cell is at most 111 seconds (median 104 seconds); none approaches the 3,600 seconds needed for a full-hour negative. All rows carry alert flag value 2, which remains subject to version-matched quality interpretation. No flashes fall inside the ERA5 rectangle. The other readable LIS granules do not provide paired atmospheric predictors because matching single- and pressure-level ERA5 is absent for their dates.

| Measure | Current result |
|---|---:|
| Candidate cell locations in the intersecting pass | 525 |
| Valid one-hour labeled samples | 0 |
| Positive one-hour labels | 0 |
| Negative one-hour labels | 0 |
| Unknown candidate cells | 525 |
| Candidate-cell state distribution | 0% positive / 0% negative / 100% unknown |
| New source paths / distinct byte contents | 1,550 / 1,130 (including one empty-file hash) |
| Source repeated-content paths | 420 |
| Zero-byte source paths | 59 |
| Unreadable non-empty HDF5 files | 1 |
| Unique readable LIS granules in canonical raw set | 1,128 |
| Exact duplicate LIS path retained in prior raw set | 1 |
| Required additional valid unique labels to reach threshold | 10,000 |

The observed zero flashes in the short LIS overpass is not evidence of a negative one-hour label. Unknown coverage stays unknown. No labels or training samples were generated, and no model was trained. The date-level LIS expansion does not change the gate because matching ERA5 surface and pressure inputs still cover only one day, and the only region-overlapping LIS observation lasts minutes.

## Additional data required

Provide real, provenance-documented ISS-LIS granules and matching ERA5 single-level **and** pressure-level data over the same dates and geographic bounds. For each candidate grid cell and target interval, LIS must include valid view-time coverage throughout the defined forecast target window, event/flash records, and interpretable quality flags. A sample can be positive when a valid observed flash occurs in that window; it can be negative only when the cell is validly observed for the complete window and no flash occurs. Partial or absent observation is unknown and excluded.

ERA5 must cover the causal history window ending at each issue time, with both surface and pressure fields available. Archive continuous or sufficiently dense, repeated co-located periods and regions to support at least 10,000 **unique** valid cell-time labels, then reserve chronological train/validation/test periods without overlapping windows or event leakage. Keep duplicate granules for audit traceability but never count them as additional samples. Do not count multiple derived rows from a single observed cell-time as independent labels.

The exact calendar duration cannot be estimated from these data. The LIS overpasses are spatially sparse, and the ERA5 archive is not co-temporal with the added July–November granules. The auditable requirement is at least 10,000 valid unique labeled cell-time samples after coverage, quality, pairing, and deduplication checks. Supply matching ERA5 single-level and pressure-level histories for the LIS periods and regions, plus repeated LIS observation windows with sufficient quality-controlled view-time coverage to support valid labels. More granules alone do not guarantee this quantity.

## Re-entry gate

Re-run the inventory and valid-observation mask after supplying the additional files. Train only after there are at least 10,000 unique valid labels and the leakage-safe chronological split and source/quality checks pass. Until then the model remains `DEMO_ONLY` and LIVE remains `BLOCKED`.
