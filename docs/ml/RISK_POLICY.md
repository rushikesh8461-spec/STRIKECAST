# Risk policy

The current API classifies the model's raw event probability with policy cutoffs. This is not calibration, a warning product, or a validated impact assessment. Status is `PROVISIONAL_UNVALIDATED` and the default version is `provisional-1`.

Defaults: LOW below 0.35; MODERATE from 0.35; HIGH from 0.60; SEVERE from 0.80. Set `RISK_MODERATE_THRESHOLD`, `RISK_HIGH_THRESHOLD`, `RISK_SEVERE_THRESHOLD`, and `RISK_POLICY_VERSION` as one coordinated deployment configuration. Values must remain ordered between 0 and 1. Configuration changes require validation against labeled operational data before LIVE use.

`/risk` returns the raw `probability`, `calibrated_probability` (null until calibrated), `calibration_status`, `risk_level`, `risk_policy_version`, `forecast_horizon_minutes`, `timestamp`, `latitude`, `longitude`, `model_version`, confidence and alert text.
