from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import time
from urllib.parse import urlparse
from typing import Any

import httpx


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _demo_strikes(latitude: float, longitude: float, timestamp: str) -> list[dict[str, Any]]:
    """Clearly marked presentation-mode strikes; never presented as observed data."""
    seed = int(hashlib.sha256(f"{latitude:.4f}:{longitude:.4f}".encode()).hexdigest()[:8], 16)
    count = 8 + seed % 7
    strikes: list[dict[str, Any]] = []
    for i in range(count):
        angle = (seed % 360 + i * 47) * math.pi / 180
        radius = 0.06 + ((seed >> (i % 16)) & 15) / 100
        age = (seed + i * 7) % 28
        strikes.append({
            "latitude": max(-90.0, min(90.0, latitude + math.sin(angle) * radius)),
            "longitude": ((longitude + math.cos(angle) * radius + 180.0) % 360.0) - 180.0,
            "timestamp": timestamp,
            "age_minutes": age,
            "polarity": 1 if i % 3 else -1,
            "intensity": None,
            "quality": None,
            "source": "StrikeCast presentation simulation",
        })
    return strikes


def _normalize(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        items = payload.get("features", [])
    elif isinstance(payload, dict) and isinstance(payload.get("strikes"), list):
        items = payload["strikes"]
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and item.get("type") == "Feature":
            coords = item.get("geometry", {}).get("coordinates", [])
            props = item.get("properties", {}) or {}
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            ts = props.get("timestamp") or props.get("time") or ""
            out.append({"latitude": lat, "longitude": lon, "timestamp": str(ts), "age_minutes": props.get("age_minutes", 0), "polarity": props.get("polarity"), "intensity": props.get("intensity"), "quality": props.get("quality")})
            continue
        if isinstance(item, dict):
            try:
                lat = float(item.get("latitude", item.get("lat")))
                lon = float(item.get("longitude", item.get("lon")))
            except (TypeError, ValueError):
                continue
            out.append({
                "latitude": lat,
                "longitude": lon,
                "timestamp": str(item.get("timestamp", item.get("time", ""))),
                "age_minutes": item.get("age_minutes", 0),
                "polarity": item.get("polarity", item.get("pol")),
                "intensity": item.get("intensity"),
                "quality": item.get("quality"),
            })
    return out


def get_lightning(latitude: float, longitude: float) -> dict[str, Any]:
    mode = os.getenv("LIGHTNING_MODE", "demo").lower()
    feed_url = os.getenv("LIGHTNING_FEED_URL", "").strip()

    if mode == "live" and feed_url:
        parsed = urlparse(feed_url)
        allowlist = {host.strip().lower() for host in os.getenv("LIGHTNING_FEED_ALLOWED_HOSTS", "").split(",") if host.strip()}
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.hostname.lower() not in allowlist:
            return {"mode": "none", "source_mode": "UNAVAILABLE", "source": "Configured lightning provider is not allowlisted", "updated_at": _now(), "strikes": []}
        headers = {"Accept": "application/json"}
        token = os.getenv("LIGHTNING_FEED_BEARER", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        for attempt in range(2):
            try:
                with httpx.Client(timeout=8.0, follow_redirects=False) as client:
                    with client.stream("GET", feed_url, headers=headers) as response:
                        if 300 <= response.status_code < 400:
                            raise ValueError("Lightning provider redirects are blocked")
                        response.raise_for_status()
                        if "application/json" not in response.headers.get("content-type", "").lower():
                            raise ValueError("Provider did not return JSON")
                        length = int(response.headers.get("content-length", "0") or 0)
                        if length > 1_000_000:
                            raise ValueError("Provider response exceeded size limit")
                        chunks = bytearray()
                        for chunk in response.iter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 1_000_000:
                                raise ValueError("Provider response exceeded size limit")
                        strikes = _normalize(json.loads(chunks))
                valid = [s for s in strikes if _valid_strike(s)]
                safe_source = f"{parsed.scheme}://{parsed.hostname}"
                deduplicated: dict[tuple[str, str, str, Any], dict[str, Any]] = {}
                for strike in valid:
                    quality = strike.get("quality")
                    if quality is not None:
                        try:
                            quality = float(quality)
                        except (TypeError, ValueError):
                            continue
                        if not math.isfinite(quality) or not 0 <= quality <= 1:
                            continue
                    strike["quality"] = quality
                    strike["source"] = safe_source
                    key = (strike["timestamp"], str(strike["latitude"]), str(strike["longitude"]), strike.get("polarity"))
                    deduplicated[key] = strike
                return {"mode": "live", "source_mode": "REAL", "source": safe_source, "updated_at": _now(), "strikes": list(deduplicated.values())[:500]}
            except Exception:
                if attempt == 0:
                    time.sleep(0.2)
        return {"mode": "none", "source_mode": "UNAVAILABLE", "source": "Configured live feed unavailable", "updated_at": _now(), "strikes": []}

    if mode == "off":
        return {"mode": "none", "source_mode": "UNAVAILABLE", "source": "Lightning feed disabled", "updated_at": _now(), "strikes": []}

    if mode == "live":
        return {"mode": "none", "source_mode": "UNAVAILABLE", "source": "Live lightning provider unavailable or unconfigured", "updated_at": _now(), "strikes": []}

    if mode != "demo":
        return {"mode": "none", "source_mode": "UNAVAILABLE", "source": "Lightning provider mode is invalid", "updated_at": _now(), "strikes": []}

    demo_time = "2026-01-01T00:00:00+00:00"
    return {"mode": "demo", "source_mode": "DEMO", "source": "StrikeCast presentation simulation", "updated_at": demo_time, "strikes": _demo_strikes(latitude, longitude, demo_time)}


def _valid_strike(strike: dict[str, Any]) -> bool:
    try:
        lat, lon = float(strike["latitude"]), float(strike["longitude"])
        stamp = datetime.fromisoformat(str(strike["timestamp"]).replace("Z", "+00:00"))
        age = float(strike.get("age_minutes", 0))
        intensity = strike.get("intensity")
        if intensity is not None and not math.isfinite(float(intensity)):
            return False
        return (-90 <= lat <= 90 and -180 <= lon <= 180 and stamp.tzinfo is not None
                and math.isfinite(age) and 0 <= age <= 10080
                and strike.get("polarity") in (None, -1, 1))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
