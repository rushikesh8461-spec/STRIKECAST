# Hackathon demo report

## Supported demo path

1. Open the existing StrikeCast Command Center.
2. Show the model/data status and explain that the served model is `DEMO_ONLY` and LIVE is blocked.
3. Show the uploaded-data inventory, checksums, and the date/space mismatch between the 2025 ERA5 archive and 2023 LIS orbits.
4. Show the one intersecting LIS orbit's sparse view-time coverage and explain why an unobserved cell is unknown rather than lightning-negative.
5. Show the existing API health/metadata and label the forecast display as a deterministic demo output.
6. Close with the limitations and the additional data needed: multi-month co-located ERA5 single/pressure-level data and quality-controlled LIS coverage sufficient for complete forecast target windows.

## Unsupported demo items

There is no real-data predicted probability map, calibrated probability, held-out prediction-vs-observation comparison, real risk map, or model explanation. Do not show the LIS orbit as a test-set result; it has not been paired into valid forecast samples. Do not present demo risk thresholds or bundled model scores as empirically validated.
