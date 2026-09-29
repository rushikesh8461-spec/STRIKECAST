"""Versioned served tensor schema used by the demo checkpoint and API."""

SERVED_FEATURE_SCHEMA_VERSION = "strikecast-served-point-v1"
SERVED_NORMALIZATION_VERSION = "point-feature-minmax-v1"
SERVED_FEATURE_NAMES = (
    "temperature_c", "humidity_pct", "pressure_hpa", "wind_speed_ms",
    "cape_jkg", "cin_jkg", "precipitation_mm_h", "data_quality",
)
SERVED_FEATURE_RANGES = {
    "temperature_c": (-10, 50), "humidity_pct": (0, 100), "pressure_hpa": (950, 1050),
    "wind_speed_ms": (0, 50), "cape_jkg": (0, 5000), "cin_jkg": (-500, 0),
    "precipitation_mm_h": (0, 100), "data_quality": (0, 1),
}
