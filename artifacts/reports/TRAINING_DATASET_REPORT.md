# Training dataset report

Status: **NO REAL DATASET CONSTRUCTED**. The strict paired NPZ contract was not satisfied: 0 provenance-complete real dataset manifests were found. The existing `data/processed/research/` arrays are research/demo preprocessing outputs and are not promoted or called real data.

The ERA5 request has 650 hourly predictor timestamps (4 present in both products, 646 missing). Data outside this exact request was not processed. An ERA5 time match cannot create a lightning label: LIS view-time must cover a complete target interval under reviewed quality policy. The only date with both ERA5 products has a sparse domain pass; other domain dates do not have both products.

No canonical samples were built. Counts of POSITIVE/NEGATIVE/UNKNOWN labels by split are therefore **not enumerated**, rather than treating unobserved cells as negatives. On the common-date overpass, 525 nominal cells remain unknown as recorded in the source audit. Dataset version: `NOT_CREATED_BLOCKED`.
