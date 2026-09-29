# Uploaded dataset inventory

Inventory regenerated from the preserved inputs and the historical data folder on 2026-09-28. The external source folder is `NEW DATA/` (read-only); its SHA-256 provenance is recorded in [`historical_lis_ingestion.json`](../../data/database/manifests/historical_lis_ingestion.json). The canonical raw manifest now contains 1,134 paths: 1,131 LIS NetCDF paths and 3 ERA5 archives. Of the LIS paths, 1,128 unique files opened and yielded metadata, 1 exact repeated raw file was de-duplicated, 1 unique file is empty, and 1 small HDF5 file is unreadable. The previous 2025 ERA5 project-root mirror remains separately recorded and is not another dataset. The machine-readable record includes variable schemas/attributes, checksums, GRIB field signatures, grids, and archive checks; rebuild with `python scripts/data/inventory_uploaded_data.py` after installing `requirements-data.txt`.

## Summary

| Dataset group | Provider/product evidence | Coverage and grid | Contents | Status |
|---|---|---|---|---|
| `1a471159767277a115d1576cda89af40.zip` | GRIB keys identify ECMWF, class `ea`, expver `0001`, stream `oper`, analyses; pressure-level ERA5 metadata | 2023-11-16 00:00–23:00 UTC; 8–20 N, 72–82 E; 0.25 degree, 49 x 41 | 1,176 messages; `q,r,t,u,v,w,z` at 1,000, 925, 850, 700, 500, 300, 200 hPa; 24 times per field/level | ZIP CRC PASS; metadata parse PASS |
| `91e9f8f6b43717c11c2515cb126d4dfe.zip` | ECMWF GRIB keys identify ERA5 single-level analysis | 2023-11-16 00:00–23:00 UTC; 8–20 N, 72–82 E; 0.25 degree and selected wave fields at 0.5 degree | 360 messages; 15 fields including 2m temperature/dewpoint, 10m wind, pressure, cloud, precipitation, BLH/CBH, and three wave fields | ZIP CRC PASS; metadata parse PASS |
| `cfb89d26495191f378f140d9833f4a6d.zip` | ECMWF GRIB keys identify ERA5 single-level analysis | 2025-04-01 00:00–2025-12-31 23:00 UTC; same regional bounds and 0.25/0.5 degree grids | 118,800 messages; 18 fields, 6,600 messages each; includes surface, wave, four ice-layer temperatures, and min/max temperature | ZIP CRC PASS; metadata parse PASS; no time overlap with 2023 LIS |
| ISS-LIS historical collection | NetCDF filenames indicate ISS-LIS V3.0 FIN; embedded globals say converted from HDF4 LIS science data and CF-1.6 but do not establish DOI/license/provider accession. | 1,128 unique readable granules; actual orbit starts 2023-07-05 05:08:49.8 through 2023-11-16 20:30:42.4 UTC; view-time bounds span -56.25 to 55.25 latitude and -179.75 to 179.75 longitude | 1,118 files have 147 variables and lightning tables; 10 have 60 variables, zero flash/event summary counts, and no event arrays; 59 zero-byte source paths and one 12,699-byte unreadable HDF source are rejected | Hash deduplication and metadata inventory complete; provenance/license and version-matched alert-flag semantics still need confirmation |

ERA5 is identified from GRIB metadata (`centre=ecmf`, `class=ea`, `expver=0001`); ECMWF documents those keys for final ERA5, and distinguishes ERA5T as expver `0005` ([ECMWF ERA5 GRIB identifiers](https://confluence.ecmwf.int/pages/viewpage.action?pageId=414588701)). ERA5 single-level and pressure-level collections are separate products ([ERA5 data documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=179741903)).

The 2023 single-level archive mixes analyses and forecast-type fields: `cbh` and accumulated `tp` are forecast products; the three `mwd/mwp/swh` fields are on the wave stream. The 2025 archive also contains forecast-type `mn2t`, `mx2t`, and `tp`. Forecast reference cycles and step ranges are retained in the JSON inventory. They need issue-time/accumulation-aware alignment before any use as causal predictors; valid time alone is insufficient.

## Original 2023-11-16 LIS files

SHA-256 is computed over the original files. One duplicate filename is intentionally preserved as supplied; its hash confirms byte identity.

| File | SHA-256 | Orbit | UTC interval (start to derived end) | Flashes / groups / events |
|---|---|---:|---|---:|
| `ISS_LIS_SC_V3.0_20231116_080740_FIN (1).nc` | `6204ef6684fdd7f14aa46a06759bec56df2b5e4de485937ebb52319b5a247060` | 80740 | 08:07:40–09:40:33 | 453 / 3,406 / 13,334 |
| `ISS_LIS_SC_V3.0_20231116_080740_FIN.nc` | `6204ef6684fdd7f14aa46a06759bec56df2b5e4de485937ebb52319b5a247060` | duplicate | duplicate bytes | duplicate |
| `ISS_LIS_SC_V3.0_20231116_094033_FIN.nc` | `9eff11b152da02616185fd419920e470f4a6ca5e530d7eb699a37471e86b2dd7` | 94033 | 09:40:33–11:13:26 | 3 / 9 / 76 |
| `ISS_LIS_SC_V3.0_20231116_111326_FIN.nc` | `8fe10e18cbbc5703663ce527a65cd3d6c04a98566d39fcf50d04a07da01f2f98` | 111326 | 11:13:26–12:46:18 | 27 / 104 / 347 |
| `ISS_LIS_SC_V3.0_20231116_124618_FIN.nc` | `9b15b32e615ac22b7736c730122cab38ac5ff282820969752d705b3581b83d69` | 124618 | 12:46:18–14:19:12 | 68 / 497 / 1,624 |
| `ISS_LIS_SC_V3.0_20231116_141912_FIN.nc` | `48cdb36d71ce881728bb82abda5f0a4c085981afd1e266f74de8dd96da4d8ffc` | 141912 | 14:19:12–15:52:04 | 224 / 1,693 / 6,100 |
| `ISS_LIS_SC_V3.0_20231116_155204_FIN.nc` | `8f5b9d5a64c05ac3c582bf4281bb130fb605e52bfcfa5d4244c4e0b938bf06ea` | 155204 | 15:52:04–17:24:57 | 54 / 402 / 2,171 |
| `ISS_LIS_SC_V3.0_20231116_185750_FIN.nc` | `11b9d384880ec423f16896c0628b6b3e37b5acac07ee067a97773429841afd6d` | 185750 | 18:57:50–20:30:42 | 313 / 2,399 / 7,600 |

No supplied 2025 ERA5 archive overlaps the LIS date. A temporal intersection exists only between the two 2023 ERA5 archives and the LIS files dated 2023-11-16. It is not continuous: the orbit sequence has a gap from about 17:24:57 to 18:57:50 UTC.

## Historical LIS ingestion

The read-only `NEW DATA/` tree contained 1,550 `.nc` paths in two collections of 362 and 1,188 files. The SHA-256 manifest found 1,130 distinct byte contents including the empty-file hash, 420 paths that repeat content, and 7 contents already present in the prior raw set. There are 1,129 distinct non-empty contents: 1,128 open as NetCDF/HDF5; one 12,699-byte HDF5 file fails to open. Fifty-nine input paths are zero bytes and are not science granules. Of the historical content, 1,123 previously absent hashes were copied under `data/raw/lightning/historical_lis/`; this includes one empty-file representative, so 1,122 non-empty new raw files were added. Original source files were left unchanged. The second collection contains the first as a same-name, same-size subset; SHA-256 relationships are retained per source path in the ingestion manifest.

## Spatial and temporal pairing result

The ERA5 regional grid is 8–20 N, 72–82 E (49 x 41 at 0.25 degree for atmospheric fields; wave fields use 0.5 degree). The LIS view-time grid uses 0.5-degree cell centers. Of the 525 nominal LIS centers in the ERA5 rectangle, only orbit 111326 has view-time rows there: 991 rows across 345 distinct centers, approximately 11:38:53–11:44:37 UTC. Those rows sum to 26,436.64 effective observation-seconds across cells and carry alert flag value 2. No LIS flashes/events fall within the rectangle in the supplied orbit. The other six distinct orbits have no view-time centers in that ERA5 rectangle.

The one-step ERA5 cadence is hourly, but the overlapping LIS coverage consists of brief cell observations, not continuous one-hour coverage. Among 345 observed cells, the median union of view-time intervals is 104 seconds and the maximum is 111 seconds; no cell reaches 3,600 seconds. All 991 rows carry alert flag 2. Thus no 60-minute negative target can be assigned. For the nominal 525 spatial cells at this overpass, valid one-hour labels are **0 positive, 0 negative, 525 unknown**. No flashes fall in the ERA5 rectangle; the zero in-rectangle count is not a valid negative forecast label. There are **0 unique valid paired training samples**; the 10,000-sample target is unsupported by these uploads.

## Continuation upload result

The historical collection extends LIS orbit coverage to July 2023 but contains no additional ERA5. Matching single-level and pressure-level ERA5 remains limited to 2023-11-16 00:00–23:00 UTC. Metadata filtering finds 177 domain-intersecting granules across 76 UTC dates; the complete intervals and hourly ERA5 requirement are in [`ERA5_REQUIRED_COVERAGE.md`](ERA5_REQUIRED_COVERAGE.md) and [`era5_required_coverage.json`](../../data/database/manifests/era5_required_coverage.json). Orbit 111326 is the only domain-intersecting pass on the currently ERA5-covered date: 991 view-time rows across 345 centers, approximately 11:38:53–11:44:37 UTC, no in-domain flashes/events, and all view-time rows carry alert flag 2. The 2025 ERA5 archive still has no LIS or pressure-level match. The valid one-hour paired sample count remains 0. See [`DATA_REQUIREMENT_FOR_10K.md`](DATA_REQUIREMENT_FOR_10K.md) for the additional labeled-data requirements.

| Period | LIS observation coverage | ERA5 single-level | ERA5 pressure-level | Spatial overlap | Usable target overlap / candidate intervals |
|---|---|---|---|---|---|
| 2023-07-05–2023-11-16 | 1,128 unique readable granules, orbital sampling; only orbit 111326 intersects the ERA5 rectangle on the matching date, 11:38:53–11:44:37 UTC | No matching files before 2023-11-16; 00:00–23:00 UTC on that day | No matching files before 2023-11-16; 00:00–23:00 UTC on that day | On the common day, 345 observed 0.5-degree centers among 525 nominal cells in 8–20 N, 72–82 E | One sparse overpass; maximum per-cell observed union 111 seconds, no in-rectangle flashes; 0 valid labels, 525 unknown candidate cells |
| 2025-04-01–2025-12-31 | None supplied | 00:00–23:00 UTC for dates in archive | None supplied | ERA5 regional grid exists, but no LIS footprint/time intersection | None; no LIS targets and no pressure-level match |

This is an observation-coverage intersection, not simply a date intersection. The LIS observed cell-time sum is finite and sparse; it cannot be expanded to intervals the sensor did not observe. The pressure-level archive only matches the 2023 date, while the 2025 ERA5 archive cannot be paired with LIS or pressure data.

## Raw preservation

Original copies are under `data/raw/era5/`, `data/raw/era5_pressure/`, and `data/raw/lightning/`. Extracted GRIB members, unchanged byte payloads, are under `data/interim/era5/` and `data/interim/pressure/`. Original files in Downloads were left untouched. No prepared paired tensors or labels were generated.
