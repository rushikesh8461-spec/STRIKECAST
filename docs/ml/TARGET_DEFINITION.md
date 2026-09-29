# Target definition and limitations

## Observation states and mask

Each target cell is `POSITIVE`, `NEGATIVE`, or `UNKNOWN`. `POSITIVE` means at least the configured number of quality-accepted events in the target interval. `NEGATIVE` requires complete, quality-accepted LIS view-time coverage of that entire interval and zero accepted events. Every other cell is `UNKNOWN`.

The canonical target array is paired with a same-shaped boolean `target_observation_mask`. Unknown storage values are placeholders only; they MUST be excluded from training loss, metrics, baselines, calibration, and class counts. The mask is true only when view-time covers the complete half-open target interval and passes the versioned quality policy. The strict prepared dataset requires `target_observation_mask_<split>` for every split.

`build_observation_aware_target` in `ml/research/strikecast/src/preprocessing/target.py` implements these states. The older unmasked `build_target_grid` helper is restricted to demo fixtures because it cannot distinguish an observed zero from unobserved time.

## Research target (version `lightning_occurrence_at_horizon_v1`)

The research preprocessing path targets binary cell-level lightning occurrence. With `strike_count >= occurrence_threshold_strikes` (default 1) inside a configured grid cell at each future timestep, target is positive; otherwise negative. For an input window whose final timestamp is `t` and configured horizon is `H` cadence steps, target indices are `t+1` through `t+H`; the output tensor is `[H, latitude, longitude]`. The target is occurrence at each forecast step, not “any event during the whole horizon.” Packaged config defaults to one future timestep. Grid, units, event detection, aggregation and event counts must come from the dataset manifest and be reported with any real experiment.

## Served point demo output

The API point output is a synthetic-demo classifier score from the bundled ConvLSTM. It is not trained against or semantically tied to the research grid-cell lightning-occurrence target. Therefore the score must not be described as an evaluated probability of lightning within a radius/time window. The API has no validated point-target definition.

## Required before model acceptance

Specify event source and detection quality; positive/negative definition; spatial radius or cell geometry; forecast horizon and target timestep; handling of events at boundaries; prevalence and censoring; and label quality. Match the model output shape and evaluation splits to that definition. Current target/data status is `NOT_READY` for operational forecasting.
