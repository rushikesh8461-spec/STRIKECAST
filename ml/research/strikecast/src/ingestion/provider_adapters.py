"""Read-only ERA5 GRIB and ISS LIS NetCDF adapters with source provenance."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import math
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any, Callable
import zipfile

from .providers import ProviderMetadata


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class FileProvider:
    def __init__(self, root: str | Path, metadata: ProviderMetadata, *, extensions: tuple[str, ...], decoder: Callable[[Path], Any] | None = None):
        self.root = Path(root).resolve()
        self.metadata = metadata
        self.extensions = tuple(ext.lower() for ext in extensions)
        self.decoder = decoder
        metadata.validate()

    def _resolve(self, source: str | Path) -> Path:
        path = (self.root / source).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("source path escapes configured provider root")
        if not path.is_file() or path.suffix.lower() not in self.extensions:
            raise ValueError("source is missing or has an unsupported extension")
        return path

    def inventory(self) -> list[dict[str, Any]]:
        return [{"path": p.relative_to(self.root).as_posix(), "bytes": p.stat().st_size, "sha256": _sha256(p)}
                for p in sorted(self.root.rglob("*")) if p.is_file() and p.suffix.lower() in self.extensions]

    def validate(self) -> list[dict[str, Any]]:
        output = []
        for row in self.inventory():
            try:
                self.load(row["path"])
                output.append({**row, "valid": True, "reason": None})
            except Exception as exc:
                output.append({**row, "valid": False, "reason": f"{type(exc).__name__}: {exc}"})
        return output

    def manifest(self) -> dict[str, Any]:
        return {"provider_metadata": asdict(self.metadata), "files": self.inventory()}

    def coverage(self) -> dict[str, Any]:
        return self.metadata.coverage

    def schema(self) -> dict[str, Any]:
        return {"variables": list(self.metadata.variables), "units": dict(self.metadata.units), "spatial_coordinates": ["lat", "lon"], "time_range": list(self.metadata.time_range)}

    def checksum(self, source: str) -> str:
        return _sha256(self._resolve(source))

    def load(self, source: str) -> Any:
        path = self._resolve(source)
        return self.decoder(path) if self.decoder else self.decode(path)

    def decode(self, path: Path) -> Any:
        raise NotImplementedError

    def provenance(self, source: str) -> dict[str, Any]:
        return {"path": Path(source).as_posix(), "sha256": self.checksum(source), "provider": self.metadata.provider,
                "source": self.metadata.source, "license": self.metadata.license, "dataset_version": self.metadata.dataset_version}


def _messages(path: Path):
    try:
        from eccodes import codes_get, codes_get_array, codes_grib_new_from_file, codes_release
    except ImportError as exc:
        raise RuntimeError("ecCodes is required to decode ERA5 GRIB") from exc
    with path.open("rb") as stream:
        count = 0
        while handle := codes_grib_new_from_file(stream):
            try:
                date, hm = int(codes_get(handle, "validityDate")), int(codes_get(handle, "validityTime"))
                from datetime import datetime, timezone
                valid = datetime.strptime(f"{date:08}{hm:04}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                short = str(codes_get(handle, "shortName"))
                levtype = str(codes_get(handle, "typeOfLevel"))
                level = int(codes_get(handle, "level")) if levtype == "isobaricInhPa" else None
                lat = codes_get_array(handle, "latitudes").astype("float64")
                lon = ((codes_get_array(handle, "longitudes").astype("float64") + 180) % 360) - 180
                values = codes_get_array(handle, "values").astype("float32")
                units = str(codes_get(handle, "units"))
                if lat.size != lon.size or values.size != lat.size or not values.size or not __import__('numpy').isfinite(values).all():
                    raise ValueError("GRIB has invalid grid coordinates or non-finite values")
                yield {"valid_time_utc": valid.isoformat(), "short_name": short, "level_hpa": level,
                       "level_type": levtype, "units": units, "latitude": lat, "longitude": lon, "values": values}
                count += 1
            finally:
                codes_release(handle)
        if not count:
            raise ValueError("GRIB contains no decodable messages")


def _canonical_grib_names() -> dict[tuple[str, int | None], str]:
    """Read the sole channel-name mapping from the checked-in feature schema."""
    try:
        import yaml
        schema_path = Path(__file__).resolve().parents[5] / "configs/data/feature_schema.yaml"
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        mapping = {}
        for field in schema["sources"]["era5_single_levels"]["fields"]:
            mapping[(str(field["grib_short_name"]), None)] = str(field["id"])
        for level in schema["sources"]["era5_pressure_levels"]["levels_hpa"]:
            for field in schema["sources"]["era5_pressure_levels"]["fields"]:
                mapping[(str(field["grib_short_name"]), int(level))] = f"{field['id']}@{int(level)}hPa"
        return mapping
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("feature_schema.yaml is unreadable or invalid") from exc


class ERA5Provider(FileProvider):
    def __init__(self, root: str | Path, metadata: ProviderMetadata, *, decoder=None):
        super().__init__(root, metadata, extensions=(".grib", ".grb", ".grib2", ".grb2", ".zip"), decoder=decoder)

    def decode(self, path: Path) -> dict[str, Any]:
        digest = _sha256(path)
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="strikecast-grib-") as temp:
                members = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith((".grib", ".grb", ".grib2", ".grb2"))]
                if len(members) != 1:
                    raise ValueError("ERA5 ZIP must contain exactly one GRIB member")
                info = members[0]
                p = PurePosixPath(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if p.is_absolute() or ".." in p.parts or "\\" in info.filename or mode == 0o120000 or info.file_size > 8 * 1024**3:
                    raise ValueError("unsafe or oversized GRIB ZIP member")
                target = Path(temp) / "source.grib"
                total = 0
                with archive.open(info) as src, target.open("xb") as dst:
                    while block := src.read(1024 * 1024):
                        total += len(block)
                        if total > info.file_size or total > 8 * 1024**3:
                            raise ValueError("GRIB ZIP member exceeded declared size")
                        dst.write(block)
                if total != info.file_size:
                    raise ValueError("GRIB ZIP member size mismatch")
                records = list(_messages(target))
        else:
            records = list(_messages(path))
        canonical = _canonical_grib_names()
        for record in records:
            record["canonical_name"] = canonical.get((record["short_name"], record["level_hpa"]))
        records.sort(key=lambda x: (x["valid_time_utc"], x["level_type"], x["level_hpa"] or 0, x["short_name"]))
        for r in records:
            r["source_sha256"] = digest
            r["source_file"] = path.name
        return {"source_sha256": digest, "records": records}


class LISProvider(FileProvider):
    def __init__(self, root: str | Path, metadata: ProviderMetadata, *, decoder=None):
        super().__init__(root, metadata, extensions=(".nc", ".nc4", ".cdf"), decoder=decoder)

    def decode(self, path: Path) -> dict[str, Any]:
        try:
            from netCDF4 import Dataset
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("netCDF4 and numpy are required to decode ISS LIS") from exc
        digest = _sha256(path)
        with Dataset(path, "r") as ds:
            required = {"viewtime_lat", "viewtime_lon", "viewtime_TAI93_start", "viewtime_TAI93_end", "viewtime_effective_obs", "viewtime_alert_flag",
                        "lightning_event_lat", "lightning_event_lon", "lightning_event_TAI93_time", "lightning_event_alert_flag"}
            missing = required - set(ds.variables)
            if missing:
                raise ValueError(f"LIS source lacks required variables: {sorted(missing)}")
            def arr(name):
                return np.ma.filled(ds.variables[name][:], np.nan if ds.variables[name].dtype.kind == "f" else 0)
            view = {name: arr("viewtime_" + name) for name in ("lat", "lon", "TAI93_start", "TAI93_end", "effective_obs", "alert_flag")}
            events = {name: arr("lightning_event_" + name) for name in ("lat", "lon", "TAI93_time", "alert_flag")}
            if not all(len(v) == len(view["lat"]) for v in view.values()) or not all(len(v) == len(events["lat"]) for v in events.values()):
                raise ValueError("LIS coordinate, time and quality arrays have inconsistent lengths")
            finite_view = np.isfinite(view["lat"]) & np.isfinite(view["lon"]) & np.isfinite(view["TAI93_start"]) & np.isfinite(view["TAI93_end"])
            finite_event = np.isfinite(events["lat"]) & np.isfinite(events["lon"]) & np.isfinite(events["TAI93_time"])
            if not finite_view.all() or not finite_event.all() or not np.isfinite(view["effective_obs"]).all():
                raise ValueError("LIS coordinates or observation times contain masked/non-finite required values")
            if np.any((view["lat"][finite_view] < -90) | (view["lat"][finite_view] > 90)) or np.any((events["lat"][finite_event] < -90) | (events["lat"][finite_event] > 90)):
                raise ValueError("LIS latitude outside WGS84 range")
            if np.any((view["lon"] < -180) | (view["lon"] > 360)) or np.any((events["lon"] < -180) | (events["lon"] > 360)):
                raise ValueError("LIS longitude outside supported degree range")
            if np.any(view["TAI93_end"] < view["TAI93_start"]) or np.any(view["effective_obs"] < 0):
                raise ValueError("LIS viewtime interval or effective-observation duration is invalid")
            orbit_start = ""
            if "orbit_summary_UTC_start" in ds.variables:
                raw_start = ds.variables["orbit_summary_UTC_start"][()]
                orbit_start = raw_start.decode("utf-8") if isinstance(raw_start, bytes) else str(raw_start)
            orbit_start_tai93 = float(ds.variables["orbit_summary_TAI93_start"][()]) if "orbit_summary_TAI93_start" in ds.variables else None
            return {"source_sha256": digest, "source_file": path.name,
                    "orbit_start_utc": orbit_start,
                    "orbit_start_tai93": orbit_start_tai93,
                    "time_encoding": {"variable_units": "seconds since 1993-01-01 00:00:00.000 TAI93", "utc_conversion": "not applied; source UTC orbit start retained separately"},
                    "viewtime": view, "events": events,
                    "quality_metadata": {"viewtime_alert_flag_comment": str(getattr(ds.variables["viewtime_alert_flag"], "comment", "")),
                                         "event_alert_flag_comment": str(getattr(ds.variables["lightning_event_alert_flag"], "comment", "")),
                                         "negative_label_policy": "UNKNOWN unless accepted viewtime covers the complete target interval"}}
