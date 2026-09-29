# ISS-LIS NetCDF data dictionary

## File structure inspected

The canonical raw inventory now contains 1,131 LIS file paths. SHA-256 deduplication leaves 1,130 content hashes, of which one represents an empty file; 1,128 unique non-empty NetCDF/HDF5 granules opened successfully. One earlier raw path is an exact byte duplicate, one canonical raw file is zero-byte, and one 12,699-byte HDF5 file fails to open. The historical `NEW DATA/` source had 1,550 paths across two collections; its hashes, duplicate paths, raw mappings, and validation status are in [`historical_lis_ingestion.json`](../../data/database/manifests/historical_lis_ingestion.json). The original source tree remains unchanged.

The readable product metadata spans orbit starts 2023-07-05 05:08:49.8 UTC through 2023-11-16 20:30:42.4 UTC. There are two schema shapes: 1,118 granules have 147 variables and lightning area/flash/group/event tables; 10 have 60 variables, zero flash/event summary counts, and omit the event/flash arrays. These 10 still include view-time and one-second quality records. Inventory captures all variable names, dimensions, dtypes, and attributes. Files identify themselves through their names and `history`/`Conventions` globals, but do not include a provider accession, DOI, license, or explicit version metadata beyond the filename.

The root globals are only `history` (“converted from original LIS science data product in hdf4 format”) and `Conventions=CF-1.6`. They do not establish provider accession/DOI, license, or product release. The filenames say `V3.0` and `FIN`, but the available NASA user guide describes older product versions; confirm that its detailed flag/version conventions apply before scientific filtering. The guide identifies ISS-LIS science products as flash-count/flash-density measurements and defines a 0.5-degree view-time cell with start/end TAI93 and effective observation duration ([NASA GHRC ISS-LIS User Guide](https://ghrc.nsstc.nasa.gov/pub/lis/iss/doc/isslis_dataset.pdf)).

## Variable families

| Family | Representative NetCDF variables | Meaning and use |
|---|---|---|
| Orbit summary | `orbit_summary_id_number`, `orbit_summary_UTC_start`, `orbit_summary_TAI93_start/end`, `orbit_summary_start/end_longitude`, inspection/configuration codes | Orbit identity, UTC start, TAI93 interval, path endpoints, and processing metadata. End UTC in inventory is derived from the TAI93 duration and UTC start. |
| Point summary | `point_summary_flash_count`, `group_count`, `event_count`, `vt_count`, addresses | Per-orbit counts and record offsets; counts are descriptive and are not gridded labels. |
| Background | `bg_summary_TAI93_time`, `bg_summary_lat/lon`, boresight/corners | Background imagery locations/times to interpret sensor context; these uploads contain science products, not a separately supplied background collection. |
| Area | `lightning_area_*` | Lightning-associated areas, centroid/time/duration, footprint/radiance, hierarchy counts, and alert/quality metrics. |
| Flash | `lightning_flash_TAI93_time`, `delta_time`, `observe_time`, `lat/lon`, `radiance`, `footprint`, `alert_flag`, `cluster_index`, `density_index`, `noise_index`, `glint_index` | Grouped flash centroids and their time, location, footprint, and quality tags. |
| Group | `lightning_group_*` | Groups that cluster optical events into flashes; contains times, locations, hierarchy and quality indicators. |
| Event | `lightning_event_TAI93_time`, `observe_time`, `lat/lon`, radiance/footprint, `alert_flag`, `cluster_index`, `density_index`, `noise_index`, `sza_index`, `glint_index` | Detected optical events, the lower-level observations aggregated into groups/flashes. Event counts must not be mistaken for independent flashes. |
| View time | `viewtime_TAI93_start/end`, `effective_obs`, `lat/lon`, `alert_flag`, `approx_threshold` | Cell-level sensor field-of-view coverage. Required to distinguish “observed with no event” from “not observed”; it is not continuous coverage over a forecast hour. |
| One second | `one_second_TAI93_time`, alert summary, instrument/platform/external/processing alerts, ephemeris/attitude quality, event count | High-frequency instrument and platform quality context. |
| Browse | `raster_image`, `raster_image_color_table` | Quick-look visualization, not a quantitative label grid. |

Units are recorded per variable in the machine-readable inventory. Time coordinates are TAI93 seconds (`seconds since 1993-01-01 00:00:00.000`); orbit UTC start is separately provided. Latitude/longitude are degrees north/east. View-time center spacing is 0.5 degrees; it represents sensor grid-cell centers, not ERA5's 0.25-degree atmospheric grid.

## Missingness, zero, and quality

The inspected key time/location/event variables are finite and unmasked in these files; no `_FillValue` attributes were found. A zero event/flash count alone does **not** mean a negative target. A valid no-lightning label requires valid view-time coverage for the complete target interval and acceptable quality status. Cells outside the view-time table, outside the sensor footprint, or with incomplete/invalid quality coverage are unknown.

Alert fields are bit-masked. The per-variable `comment` attributes describe instrument, platform, external, and processing flags; the observed value `2` sets the second least-significant bit, a warning flag under the NASA guide's documented convention. All 991 view-time rows in the ERA5 overlap area carry value `2`; it requires review, not silent acceptance as clean coverage. Event/flash quality scores also exist and must be interpreted using the exact product-version guide. Orbit inspection/configuration values are zero in the original seven 2023-11-16 files, but that value alone is not an independent quality certification.

## Pairing disposition

Only orbit 111326 intersects the ERA5 rectangle at 8–20 N, 72–82 E: 345 distinct 0.5-degree centers and 991 view-time rows over about 5.7 minutes. Per-cell union coverage has a 104-second median and 111-second maximum; no cell is covered for a complete one-hour target. All rows carry alert flag 2. No flashes/events fall inside the rectangle. This remains the only granule with common spatial coverage on the one date for which both ERA5 products are supplied; the rest of the expanded LIS archive lacks matching ERA5 histories. For the configured target, all 525 nominal cells are UNKNOWN: 0 POSITIVE, 0 NEGATIVE, 525 UNKNOWN. This does not assert that no lightning occurred during unobserved periods. A negative can only be assigned when the relevant cell is observed with accepted quality across the complete target interval; the available view-time rows do not establish that condition. No binary labels were generated.
