# Data dictionary (served demo)

| Field | Unit | Source / meaning | Limitation |
|---|---|---|---|
| temperature_c | °C | M1 atmospheric point | Synthetic in the served DEMO mode |
| humidity_pct | % | M1 relative humidity | Synthetic in the served DEMO mode |
| pressure_hpa | hPa | M1 surface pressure | Synthetic in the served DEMO mode |
| wind_speed_ms | m/s | M1 wind speed | Synthetic in the served DEMO mode |
| wind_direction_deg | degrees | M1 wind direction | Synthetic in the served DEMO mode |
| cape_jkg | J/kg | M1 CAPE proxy | Synthetic in the served DEMO mode |
| cin_jkg | J/kg | M1 convective inhibition | Synthetic in the served DEMO mode |
| precipitation_mm_h | mm/h | M1 precipitation | Synthetic in the served DEMO mode |
| probability | [0,1] | M3 raw event probability | Synthetic-trained model, not calibrated |
| risk_level | LOW/MODERATE/HIGH/SEVERE | M4 provisional threshold policy | Not validated for operational decisions |

The research dataset tensor contract and feature order are described in `DATASET_CONTRACT.md` and `ml/research/strikecast/src/features/schema.py`.
