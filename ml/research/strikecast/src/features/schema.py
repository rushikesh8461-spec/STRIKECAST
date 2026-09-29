"""
Feature schema — the fixed, documented channel ordering M2 hands to M3.

Every feature (base or derived) is described here as:
    FEATURE, SOURCE, FORMULA/METHOD, UNITS, DIMENSIONS, WHY IT IS USEFUL

`BASE_FEATURES` are directly-observed (post-alignment/cleaning) variables
and are always included. `DERIVED_FEATURES` are engineered from base
features and are individually toggleable via
config/preprocessing_config.yaml `features.enabled_derived_features`, so
M3 can run ablations without touching this module (spec Phase 8).

Channel order is: BASE_FEATURES (in the order below) followed by whichever
DERIVED_FEATURES are enabled, in the order they appear below. This order
is asserted by tests/preprocessing/test_channel_order.py — treat it as
part of the M2 -> M3 contract, not an implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    source: str
    formula: str
    units: str
    dimensions: str
    why: str


BASE_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        "brightness_temperature", "satellite", "as observed (post-align/clean)",
        "K", "[time, lat, lon]",
        "Primary cloud-top proxy; cold anomalies mark deep convection.",
    ),
    FeatureSpec(
        "cloud_top_height_estimate", "satellite", "as observed (post-align/clean)",
        "km", "[time, lat, lon]",
        "Taller cloud tops correlate with stronger updrafts / storm intensity.",
    ),
    FeatureSpec(
        "temperature_2m", "nwp", "as observed (post-align/clean)",
        "K", "[time, lat, lon]",
        "Surface heating drives convective initiation.",
    ),
    FeatureSpec(
        "relative_humidity", "nwp", "as observed (post-align/clean)",
        "%", "[time, lat, lon]",
        "Moisture availability is a precondition for thunderstorm development.",
    ),
    FeatureSpec(
        "surface_pressure", "nwp", "as observed (post-align/clean)",
        "hPa", "[time, lat, lon]",
        "Pressure falls often precede convective development.",
    ),
    FeatureSpec(
        "wind_u", "nwp", "as observed (post-align/clean)",
        "m/s", "[time, lat, lon]",
        "Wind shear (with wind_v) organizes and sustains storm cells.",
    ),
    FeatureSpec(
        "wind_v", "nwp", "as observed (post-align/clean)",
        "m/s", "[time, lat, lon]",
        "Wind shear (with wind_u) organizes and sustains storm cells.",
    ),
    FeatureSpec(
        "cape", "nwp", "as observed (post-align/clean)",
        "J/kg", "[time, lat, lon]",
        "Convective Available Potential Energy — the standard instability index.",
    ),
    FeatureSpec(
        "cin", "nwp", "as observed (post-align/clean)",
        "J/kg", "[time, lat, lon]",
        "Convective Inhibition — suppresses convection until eroded; rising CIN "
        "toward 0 often precedes storm initiation.",
    ),
    FeatureSpec(
        "reflectivity", "radar", "as observed (post-align/clean)",
        "dBZ", "[time, lat, lon]",
        "Direct precipitation/storm-cell intensity signal where radar coverage exists.",
    ),
    FeatureSpec(
        "lightning_strike_count", "lightning (M2-gridded)",
        "count of strikes binned into this cell/timestep (see spatial_alignment.bin_lightning_to_grid)",
        "count", "[time, lat, lon]",
        "Recent lightning activity is strongly autocorrelated — the single "
        "strongest predictor of near-term continued activity.",
    ),
    FeatureSpec(
        "lightning_mean_abs_intensity", "lightning (M2-gridded)",
        "mean(|intensity|) of strikes binned into this cell/timestep; 0 if none",
        "kA", "[time, lat, lon]",
        "Strike intensity distribution can indicate storm severity, not just presence.",
    ),
]

DERIVED_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        "wind_speed", "nwp (derived)", "sqrt(wind_u**2 + wind_v**2)",
        "m/s", "[time, lat, lon]",
        "Scalar wind magnitude is often more directly useful to a ConvLSTM "
        "than raw signed components alone.",
    ),
    FeatureSpec(
        "cape_dt", "nwp (derived)",
        "cape[t] - cape[t-1] (causal; 0 at the first available step)",
        "J/kg per step", "[time, lat, lon]",
        "Rising CAPE (building instability) is a leading indicator, not just its level.",
    ),
    FeatureSpec(
        "cin_dt", "nwp (derived)",
        "cin[t] - cin[t-1] (causal; 0 at the first available step)",
        "J/kg per step", "[time, lat, lon]",
        "CIN eroding toward 0 (rising, since CIN is <= 0) often precedes storm onset.",
    ),
    FeatureSpec(
        "reflectivity_dt", "radar (derived)",
        "reflectivity[t] - reflectivity[t-1] (causal; 0 at the first available step)",
        "dBZ per step", "[time, lat, lon]",
        "Intensifying reflectivity signals a strengthening cell.",
    ),
    FeatureSpec(
        "brightness_temperature_dt", "satellite (derived)",
        "brightness_temperature[t] - brightness_temperature[t-1] (causal; 0 at first step)",
        "K per step", "[time, lat, lon]",
        "Rapid cooling of cloud tops signals explosive convective growth.",
    ),
    FeatureSpec(
        "reflectivity_spatial_gradient_mag", "radar (derived)",
        "sqrt(d(reflectivity)/dlat**2 + d(reflectivity)/dlon**2) via central "
        "finite differences at each timestep (edges use one-sided differences)",
        "dBZ / cell", "[time, lat, lon]",
        "Sharp reflectivity gradients mark storm-cell edges/fronts, not just bulk intensity.",
    ),
    FeatureSpec(
        "lightning_recent_count_3step", "lightning (derived)",
        "causal rolling sum of lightning_strike_count over the current step "
        "and the previous (window_steps - 1) steps (window_steps configurable; "
        "name reflects the default of 3)",
        "count", "[time, lat, lon]",
        "Short-term lightning trend smooths single-step noise while staying causal.",
    ),
]

ALL_FEATURES_BY_NAME: dict[str, FeatureSpec] = {
    f.name: f for f in BASE_FEATURES + DERIVED_FEATURES
}


def resolve_channel_order(enabled_derived_features: list[str]) -> list[str]:
    """The one authoritative place that decides channel order: BASE
    features (fixed), then enabled DERIVED features in their declared
    (not the config's) order — so re-ordering the config list never
    silently changes the contract."""
    base_names = [f.name for f in BASE_FEATURES]
    enabled_set = set(enabled_derived_features)
    derived_names = [f.name for f in DERIVED_FEATURES if f.name in enabled_set]
    unknown = enabled_set - {f.name for f in DERIVED_FEATURES}
    if unknown:
        raise ValueError(f"Unknown derived feature(s) in config: {sorted(unknown)}")
    return base_names + derived_names


def get_feature_schema(enabled_derived_features: list[str]) -> list[dict]:
    """M2 -> M3 contract artifact: full per-channel documentation in
    resolved channel order."""
    order = resolve_channel_order(enabled_derived_features)
    return [ALL_FEATURES_BY_NAME[name].__dict__ for name in order]
