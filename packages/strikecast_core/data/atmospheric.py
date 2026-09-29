from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import json
import math
import time
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MAX_PROVIDER_RESPONSE_BYTES = 1_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

@dataclass(frozen=True)
class AtmosphericObservation:
    latitude: float
    longitude: float
    timestamp: str
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    wind_speed_ms: float
    wind_direction_deg: float
    cape_jkg: float
    cin_jkg: float
    precipitation_mm_h: float
    data_quality: float
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


def _synthetic_point(latitude: float, longitude: float, index: int, base_timestamp: str) -> AtmosphericObservation:
    seed = abs(latitude * 12.731 + longitude * 7.193 + index * 3.17) % 100.0
    temperature = 22.0 + 10.0 * math.sin(math.radians(latitude)) + (seed % 8.0)
    humidity = min(98.0, max(30.0, 58.0 + (seed * 0.37) % 38.0))
    pressure = 1006.0 + ((seed * 0.83) % 18.0)
    wind = 2.0 + ((seed * 0.17) % 13.0)
    wind_dir = (seed * 3.6) % 360.0
    cape = max(0.0, 250.0 + seed * 55.0)
    cin = -max(5.0, 15.0 + (seed % 80.0))
    precip = max(0.0, (seed - 62.0) * 0.14)
    point_time = datetime.fromisoformat(base_timestamp.replace("Z", "+00:00"))
    timestamp = (point_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=5-index)).isoformat()
    return AtmosphericObservation(latitude, longitude, timestamp,
        round(temperature,2), round(humidity,2), round(pressure,2), round(wind,2),
        round(wind_dir,2), round(cape,2), round(cin,2), round(precip,2), 0.72, "synthetic-fallback")


def _fetch_live(latitude: float, longitude: float) -> list[AtmosphericObservation]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,cape,convective_inhibition,precipitation",
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    url = OPEN_METEO_URL + "?" + urlencode(params)
    if not url.startswith(OPEN_METEO_URL + "?"):
        raise ValueError("Provider URL is outside the Open-Meteo allowlist")
    req = Request(url, headers={"User-Agent": "StrikeCast/1.0", "Accept": "application/json"})
    payload = None
    for attempt in range(2):
        try:
            opener = build_opener(_NoRedirect())
            with opener.open(req, timeout=8) as response:
                if response.status != 200 or "application/json" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("Open-Meteo returned an unexpected response")
                declared = int(response.headers.get("Content-Length", "0") or 0)
                if declared > MAX_PROVIDER_RESPONSE_BYTES:
                    raise ValueError("Open-Meteo response exceeded size limit")
                body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
                if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
                    raise ValueError("Open-Meteo response exceeded size limit")
                payload = json.loads(body.decode("utf-8"))
            break
        except Exception:
            if attempt:
                raise
            time.sleep(0.2)
    h = payload["hourly"]
    n = len(h["time"])
    required = ("temperature_2m", "relative_humidity_2m", "surface_pressure", "wind_speed_10m",
                "wind_direction_10m", "cape", "convective_inhibition", "precipitation")
    for key in required:
        if not isinstance(h.get(key), list) or len(h[key]) != n:
            raise ValueError(f"Open-Meteo field {key} is missing or has an invalid shape")
    start = max(0, n - 6)
    observations=[]
    for i in range(start,n):
        def val(key):
            x=h[key][i]
            if x is None:
                raise ValueError(f"Open-Meteo field {key} contains missing values")
            parsed = float(x)
            if not math.isfinite(parsed):
                raise ValueError(f"Open-Meteo field {key} contains non-finite values")
            return parsed
        time_value = str(h["time"][i])
        if datetime.fromisoformat(time_value.replace("Z", "+00:00")).tzinfo is None:
            time_value += "Z"  # Open-Meteo was explicitly requested with timezone=UTC.
        parsed_time = datetime.fromisoformat(time_value.replace("Z", "+00:00"))
        if observations and parsed_time <= datetime.fromisoformat(observations[-1].timestamp.replace("Z", "+00:00")):
            raise ValueError("Open-Meteo timestamps are not strictly increasing")
        temp, humidity, pressure = val("temperature_2m"), val("relative_humidity_2m"), val("surface_pressure")
        wind, direction, cape = val("wind_speed_10m"), val("wind_direction_10m"), val("cape")
        cin, precip = val("convective_inhibition"), val("precipitation")
        if not (-100 <= temp <= 70 and 0 <= humidity <= 100 and 800 <= pressure <= 1100
                and 0 <= wind <= 150 and 0 <= direction <= 360 and 0 <= cape <= 20000
                and -10000 <= cin <= 5000 and 0 <= precip <= 2000):
            raise ValueError("Open-Meteo returned a value outside configured physical bounds")
        observations.append(AtmosphericObservation(
            latitude=latitude, longitude=longitude, timestamp=time_value,
            temperature_c=round(temp,2),
            humidity_pct=round(humidity,2),
            pressure_hpa=round(pressure,2),
            wind_speed_ms=round(wind,2),
            wind_direction_deg=round(direction,2),
            cape_jkg=round(cape,2),
            cin_jkg=round(cin,2),
            precipitation_mm_h=round(precip,2),
            data_quality=0.97,
            source="Open-Meteo live atmospheric feed",
        ))
    if len(observations) < 6:
        raise RuntimeError("Open-Meteo returned fewer than 6 hourly observations")
    return observations


def ingest_atmospheric_data(latitude: float, longitude: float, timestamp: str | None = None, mode: str = "live") -> list[AtmosphericObservation]:
    if not math.isfinite(float(latitude)) or not -90 <= latitude <= 90: raise ValueError("latitude must be finite and between -90 and 90")
    if not math.isfinite(float(longitude)) or not -180 <= longitude <= 180: raise ValueError("longitude must be finite and between -180 and 180")
    mode = mode.strip().lower()
    if mode == "demo":
        base_timestamp = timestamp or "2026-01-01T00:00:00+00:00"
        parsed = datetime.fromisoformat(base_timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("demo timestamp must include a timezone")
        return [_synthetic_point(latitude, longitude, i, base_timestamp) for i in range(6)]
    if mode != "live":
        raise ValueError("atmospheric ingestion mode must be demo or live")
    return _fetch_live(latitude, longitude)
