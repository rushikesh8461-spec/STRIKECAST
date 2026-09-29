# Real-data leakage audit

Scope: original ERA5 uploads plus 1,128 newly readable unique LIS granules from 2023-07-05 through 2023-11-16, audited 2026-09-28. Of the readable unique LIS granules, 177 intersect the StrikeCast domain across 76 dates. Only 2023-11-16 currently has both ERA5 products; only one domain-intersecting LIS granule falls on that ERA5-covered date. This remains a dataset-readiness audit; **there are no prepared training samples**, so it cannot certify a trained model. Valid paired target samples remain 0 because complete target-hour LIS observation masks and corresponding ERA5 windows are not available.

| Leakage/control check | Status | Finding |
|---|---|---|
| Future atmospheric values | BLOCKED | ERA5 inputs are retrospective analysis fields with valid times but no issue-time availability/provenance timestamps. They cannot be represented as operationally available live inputs from these files. |
| Future lightning in features | PASS for source separation | LIS is used only as the proposed target source; no LIS predictor features were constructed. |
| Target leakage / boundary convention | BLOCKED | No event-to-grid target exists. Define an exact next-hour target and half-open time interval before construction; event/view-time data cannot enter X. |
| Train-only normalization | NOT RUN | No valid sample splits exist; future preparation must fit on TRAIN only. |
| Interpolation leakage | PASS in existing research preprocessing | Two-sided temporal interpolation has been removed; missing observations remain masked. This does not resolve unavailable-time provenance in ERA5. |
| Temporal overlap / window splits | BLOCKED | LIS intersects the domain on 76 dates, but complete paired ERA5 coverage exists only on 2023-11-16. That date has one intersecting LIS granule and does not provide enough independently observed labels for chronological train/validation/test splits. |
| Duplicate samples/files | PASS for source duplicate audit | One LIS filename pair is byte-identical and is flagged; no samples were built. Do not count it twice. |
| Storm/event overlap | BLOCKED | No event grouping or storm IDs are available in the current pairing; one day cannot support event-held-out evaluation. |
| Spatial leakage / regridding | NOT RUN | No mapping to a common grid was created. Mapping 0.5-degree LIS coverage to 0.25-degree ERA5 by resizing would create false precision and is prohibited. |
| Test contamination | PASS by non-use | No TEST examples/predictions or metrics were created or inspected. |
| Feature-engineering leakage | PASS in code review, real data blocked | Existing research features are causal and preserve masks; no real-data feature tensor was built. |

## Decision

The no-interpolation and whole-window split controls in the code remain useful. Dataset-level leakage audit is **BLOCKED**, not PASS, because the retrospective ERA5 availability times and one-hour LIS labels cannot be validated for the required issue/target protocol. The future training guide must use a dataset with issue-time-available predictors and full valid target observation coverage, preserve an untouched chronological test period, and record source lineage for every sample.
