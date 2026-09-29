# Lightning target contract

See [the research target definition](../ml/TARGET_DEFINITION.md) for the model target and existing limitations.

Every cell target is `POSITIVE`, `NEGATIVE`, or `UNKNOWN`. A negative requires complete quality-accepted LIS view-time coverage for the full half-open target interval and zero accepted events. Unobserved or quality-rejected cells are unknown. Prepared datasets carry `target_observation_mask_<split>` aligned to `y_<split>`; loss, metrics, baselines, calibration, and class counts must use only true mask entries.

The target interval is one configured cadence interval at the selected forecast lead. Event detection, target grid, cadence, quality policy, and lead are dataset-manifest fields. Do not interpolate events or infer negatives from missing files or zero event records.
