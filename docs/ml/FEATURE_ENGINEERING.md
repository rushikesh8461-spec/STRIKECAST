# Feature engineering status

## Served point path

`packages/strikecast_core/features/point.py` consumes the last six atmospheric observations and emits a deterministic `[time=6,height=3,width=3,channels=8]` sequence plus a latest-time vector. The eight ordered channels are:

| Feature | Units | Min-max bounds before normalization |
|---|---|---|
| temperature_c | °C | [-10, 50] |
| humidity_pct | % | [0, 100] |
| pressure_hpa | hPa | [950, 1050] |
| wind_speed_ms | m/s | [0, 50] |
| cape_jkg | J/kg | [0, 5000] |
| cin_jkg | J/kg | [-500, 0] |
| precipitation_mm_h | mm/h | [0, 100] |
| data_quality | unitless fraction | [0, 1] |

Wind direction is present in M1 observations but is not used by this M2 point model. Each cell in the 3×3 sequence is the same point vector plus a deterministic, small row/column offset; it is a tensor-shape device and does not represent observed neighboring locations. Values are clipped to configured ranges then min-max normalized. There is no fitted train-stat scaler in this served adapter; this limitation is part of why its output is demo-only.

The served feature builder does not fit normalization on batches or use validation/test inputs. Its scaling constants are fixed configuration in source, so this is not a learned train-only scaler and the model/data are still synthetic demo artifacts.

## Research preprocessing path

`ml/research/strikecast/src/preprocessing` and `ml/research/strikecast/src/features` build research windows from validated source arrays. Tests cover target leakage, temporal alignment, chronological split behavior, training-only normalization and deterministic feature schema. Missing values remain masked; two-sided temporal interpolation is prohibited because it can use a future observation. The strict real-data loader also requires per-feature availability timestamps no later than forecast issue time. Whole input-plus-target windows must remain in one chronological split. The sample dataset has too few windows for non-empty validation/test partitions; passing software tests does not establish that it is suitable for real forecasting.

## Constraints

- No real lightning target labels are supplied.
- No production feature artifact is registered for the point inference path.
- The real dataset contract checks schema and declared quality gates but does not independently inspect original provider data.
- Feature schema/version matching across a future real model and the serving path remains an acceptance requirement.
