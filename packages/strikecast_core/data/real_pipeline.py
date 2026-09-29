"""Canonical raw ERA5/LIS gridding and observation-aware paired samples.

The module uses deterministic bin aggregation for atmospheric grid reduction and
never interpolates lightning targets. LIS negatives require continuous accepted
viewtime coverage of the entire half-open target interval; a valid event is a
positive observation even when the remainder of that interval was not viewed.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib, json, math
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any, Iterable
import numpy as np
import yaml


class DataLeakageError(ValueError): pass
class IncompleteAtmosphericField(ValueError): pass
class FeatureCompatibilityError(ValueError): pass
class TargetPolicyPending(ValueError): pass


@dataclass(frozen=True)
class TargetPolicy:
    """Science-approved LIS policy; quality acceptance is never inferred here."""
    accepted_quality_flags: frozenset[int] | None
    policy_version: str
    approved: bool = False
    minimum_coverage_fraction: float = 1.0
    negative_label_rule: str = "complete_accepted_viewtime_only"
    viewtime_rule: str = "half_open_interval_union"

    def validate(self) -> None:
        if not self.approved or self.accepted_quality_flags is None or not self.policy_version.strip():
            raise TargetPolicyPending("TARGET_POLICY_STATUS=PENDING_APPROVAL")
        if not 0.0 < self.minimum_coverage_fraction <= 1.0:
            raise ValueError("minimum coverage fraction must be in (0,1]")
        if self.negative_label_rule!="complete_accepted_viewtime_only" or self.viewtime_rule!="half_open_interval_union":
            raise ValueError("unsupported target observation rule")


TargetObservationPolicy=TargetPolicy


@dataclass(frozen=True)
class PipelineLimits:
    max_source_file_size: int = 512 * 1024 * 1024
    max_records_in_memory: int = 5_000_000
    max_lis_records_in_memory: int = 5_000_000
    max_grid_cells: int = 100_000
    max_sequence_length: int = 24

    @classmethod
    def from_config(cls, config: dict) -> "PipelineLimits":
        raw=config.get("limits",{})
        obj=cls(**{k:int(v) for k,v in raw.items()})
        if min(obj.max_source_file_size,obj.max_records_in_memory,obj.max_lis_records_in_memory,obj.max_grid_cells,obj.max_sequence_length)<=0:
            raise ValueError("pipeline limits must be positive")
        return obj


from ..features.served_schema import (SERVED_FEATURE_NAMES, SERVED_FEATURE_SCHEMA_VERSION,
                                      SERVED_NORMALIZATION_VERSION)


class InferenceFeatureAdapter:
    """Strict bridge to the existing 6x3x3x8 served model contract.

    This research schema cannot supply CAPE/CIN; those fields are intentionally
    required explicitly and no arbitrary replacement is inferred.
    """
    def __init__(self, mapping: dict[str, str], *, schema_version: str = SERVED_FEATURE_SCHEMA_VERSION):
        if schema_version != SERVED_FEATURE_SCHEMA_VERSION:
            raise FeatureCompatibilityError("unsupported served feature schema version")
        if tuple(mapping) != SERVED_FEATURE_NAMES:
            raise FeatureCompatibilityError("mapping must declare all served feature names in canonical order")
        self.mapping = dict(mapping)
        self.schema_version = schema_version

    @staticmethod
    def validate_research_tensor(tensor: np.ndarray, research_feature_names: list[str] | tuple[str,...], *,
                                 feature_schema_version: str, normalization_version: str) -> np.ndarray:
        values=np.asarray(tensor)
        if feature_schema_version!="strikecast-era5-feature-schema-v1": raise FeatureCompatibilityError("research feature schema version mismatch")
        if normalization_version!=SERVED_NORMALIZATION_VERSION: raise FeatureCompatibilityError("research normalization cannot be silently reused as served min-max normalization")
        if values.ndim!=5 or values.shape[0]<1 or values.shape[1]!=6 or values.shape[2]!=len(research_feature_names) or values.shape[-2:]!=(3,3):
            raise FeatureCompatibilityError("expected [batch>0,6,research_channels,3,3]")
        if not np.issubdtype(values.dtype,np.number) or not np.isfinite(values).all():
            raise FeatureCompatibilityError("model input must be finite numeric values")
        if len(set(research_feature_names))!=len(research_feature_names): raise FeatureCompatibilityError("research feature names must be unique")
        return values

    def map_to_served_tensor(self, tensor: np.ndarray, research_feature_names: list[str] | tuple[str,...]) -> np.ndarray:
        values=np.asarray(tensor); indexes={name:i for i,name in enumerate(research_feature_names)}
        missing=[source for source in self.mapping.values() if source not in indexes]
        if missing: raise FeatureCompatibilityError("required served features cannot be derived: "+", ".join(missing))
        return np.stack([values[:,:,indexes[self.mapping[name]],:,:] for name in SERVED_FEATURE_NAMES],axis=2).astype(np.float32)

    @staticmethod
    def validate_served_tensor(tensor: np.ndarray, *, served_feature_schema_version: str,
                               normalization_version: str) -> np.ndarray:
        values=np.asarray(tensor)
        if served_feature_schema_version!=SERVED_FEATURE_SCHEMA_VERSION: raise FeatureCompatibilityError("served feature schema version mismatch")
        if normalization_version!=SERVED_NORMALIZATION_VERSION: raise FeatureCompatibilityError("served normalization version mismatch")
        if values.ndim!=5 or values.shape[0]<1 or tuple(values.shape[1:])!=(6,8,3,3): raise FeatureCompatibilityError("expected served [batch>0,6,8,3,3] tensor")
        if values.dtype!=np.float32 or not np.isfinite(values).all(): raise FeatureCompatibilityError("served tensor must be finite float32")
        return values

    def adapt(self, tensor: np.ndarray, research_feature_names: list[str] | tuple[str, ...], *,
              feature_schema_version: str, normalization_version: str) -> np.ndarray:
        values=self.validate_research_tensor(tensor,research_feature_names,feature_schema_version=feature_schema_version,
                                             normalization_version=normalization_version)
        served=self.map_to_served_tensor(values,research_feature_names)
        return self.validate_served_tensor(served,served_feature_schema_version=self.schema_version,
                                           normalization_version=normalization_version)


class LISObservationIndex:
    """Cell-indexed references into decoded granules; lookup avoids universe scans."""
    def __init__(self, granules: Iterable[dict], latitude: np.ndarray, longitude: np.ndarray, resolution: float):
        self.granules=list(granules)
        self.by_hour: dict[datetime,set[int]] = {}
        self.by_time_cell: dict[tuple[datetime,tuple[int,int]],list[tuple[str,int,int,datetime]]] = {}
        self.cells: set[tuple[int,int]] = set()
        self.times: list[datetime] = []
        self.lookup_calls=0; self.records_returned=0
        for gi,g in enumerate(self.granules):
            orbit=g.get("orbit_start_utc"); tai0=float(g.get("orbit_start_tai93",0.0))
            v=g["viewtime"]
            _validate_source_coordinates(np.asarray(v["lat"],dtype=np.float64),np.asarray(v["lon"],dtype=np.float64))
            _validate_source_coordinates(np.asarray(g["events"]["lat"],dtype=np.float64),np.asarray(g["events"]["lon"],dtype=np.float64))
            for ri,(lat,lon,t,tend) in enumerate(zip(v["lat"],v["lon"],v["TAI93_start"],v["TAI93_end"])):
                cell=align_spatial_cell(lat,lon,latitude,longitude,resolution)
                if cell is not None:
                    stamp=_lis_datetime(t,orbit,tai0); end_stamp=_lis_datetime(tend,orbit,tai0)
                    row=("view",gi,ri,stamp); self.by_time_cell.setdefault((stamp,cell),[]).append(row); self.cells.add(cell); self.times.append(stamp)
                    hour=stamp.replace(minute=0,second=0,microsecond=0)
                    while hour<end_stamp:
                        self.by_hour.setdefault(hour,set()).add(gi); hour+=timedelta(hours=1)
                    if end_stamp<=stamp: self.by_hour.setdefault(hour,set()).add(gi)
            e=g["events"]
            for ri,(lat,lon,t) in enumerate(zip(e["lat"],e["lon"],e["TAI93_time"])):
                cell=align_spatial_cell(lat,lon,latitude,longitude,resolution)
                if cell is not None:
                    stamp=_lis_datetime(t,orbit,tai0); row=("event",gi,ri,stamp); self.by_time_cell.setdefault((stamp,cell),[]).append(row); self.cells.add(cell); self.times.append(stamp); self.by_hour.setdefault(stamp.replace(minute=0,second=0,microsecond=0),set()).add(gi)
        self.times=sorted(set(self.times))

    def lookup(self, timestamp: datetime, cell: tuple[int,int]) -> tuple[tuple[str,int,int,datetime], ...]:
        stamp=_parse_time(timestamp)
        self.lookup_calls+=1; result=tuple(self.by_time_cell.get((stamp,cell),())); self.records_returned+=len(result)
        return result

    query=lookup

    def query_time_range(self, start: datetime, end: datetime, cell: tuple[int,int] | None=None) -> tuple[tuple[str,int,int,datetime], ...]:
        start=_parse_time(start); end=_parse_time(end)
        lo=bisect_left(self.times,start); hi=bisect_left(self.times,end)
        stamps=self.times[lo:hi]
        if cell is not None: return tuple(item for stamp in stamps for item in self.by_time_cell.get((stamp,cell),()))
        return tuple(item for stamp in stamps for key_cell in self.cells for item in self.by_time_cell.get((stamp,key_cell),()))

    def granules_for(self, start: datetime, end: datetime) -> list[dict]:
        """Fetch only granules with indexed records in the requested time span."""
        start=_parse_time(start); end=_parse_time(end)
        keys=set(); hour=start.replace(minute=0,second=0,microsecond=0)
        while hour<end:
            keys.update(self.by_hour.get(hour,set())); hour+=timedelta(hours=1)
        return [self.granules[i] for i in sorted(keys)]


LISIndex=LISObservationIndex


class PersistenceBaseline:
    """Persistence evaluation uses a prior observed target grid, never ERA5 features."""
    @staticmethod
    def predict(target: np.ndarray, observation_mask: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
        value=np.asarray(target,dtype=np.float32); mask=np.asarray(observation_mask,dtype=bool)
        if value.shape != mask.shape or value.ndim != 2:
            raise ValueError("persistence requires matching 2D target and observation grids")
        if not mask.any(): raise ValueError("persistence prior target has no observed cells")
        return value.copy(),mask.copy()

    @classmethod
    def for_sample(cls, sample: dict, history: Iterable[dict]) -> dict[str, Any]:
        cutoff=_parse_time(sample["prediction_time"])
        eligible=[row for row in history if _parse_time(row["target_interval_utc"][1])<cutoff
                  and np.asarray(row["observation_mask"],dtype=bool).any()]
        if not eligible:
            return {"status":"NOT_APPLICABLE","reason":"No prior observed target grid strictly before prediction time."}
        prior=max(eligible,key=lambda row:_parse_time(row["target_interval_utc"][1]))
        values,mask=cls.predict(prior["target"],prior["observation_mask"])
        return {"status":"READY","target":values,"observation_mask":mask,"source_sample_id":prior.get("sample_id"),
                "source_interval_end_utc":_parse_time(prior["target_interval_utc"][1]).isoformat()}


@dataclass
class CanonicalPairedDataset:
    samples: list[dict[str, Any]]
    latitude: np.ndarray
    longitude: np.ndarray
    feature_names: list[str]
    feature_schema_version: str
    target_schema_version: str
    manifest: dict[str, Any]

    @property
    def counts(self) -> dict[str, int]:
        total = len(self.samples)
        pos = sum(int(s["target"][s["observation_mask"]].sum()) for s in self.samples)
        obs = sum(int(s["observation_mask"].sum()) for s in self.samples)
        return {"candidate_samples": self.manifest.get("candidate_samples", total), "valid_samples": total,
                "positive_cells": pos, "negative_cells": obs-pos,
                "unknown_cells": sum(int((~s["observation_mask"]).sum()) for s in self.samples),
                "missing_features": int(self.manifest.get("missing_features", 0)),
                "missing_targets": int(self.manifest.get("missing_targets", 0))}


def load_feature_schema(path: str | Path) -> dict:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("sources"), dict):
        raise ValueError("invalid feature schema")
    return value


def _grid(schema: dict) -> tuple[np.ndarray, np.ndarray, float]:
    cfg = schema["grid"]; step = float(cfg["canonical_resolution_degrees"] if "canonical_resolution_degrees" in cfg else cfg.get("target_resolution_degrees", cfg.get("resolution_degrees", 0.5)))
    # The current schema declares the canonical target at 0.5 degrees via the
    # training config; use the configured resolution passed by caller below.
    south, north, west, east = map(float, (cfg["south"],cfg["north"],cfg["west"],cfg["east"]))
    lat = np.arange(south+step/2, north, step, dtype=np.float64)
    lon = np.arange(west+step/2, east, step, dtype=np.float64)
    return lat, lon, step


def _parse_time(v: str | datetime) -> datetime:
    d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if d.tzinfo is None: raise ValueError("timestamps require UTC offset")
    return d.astimezone(timezone.utc)


def _validate_source_coordinates(latitude: np.ndarray, longitude: np.ndarray) -> None:
    if not np.isfinite(latitude).all() or not np.isfinite(longitude).all(): raise ValueError("source coordinates must be finite")
    if ((latitude < -90) | (latitude > 90)).any() or ((longitude < -180) | (longitude > 360)).any():
        raise ValueError("source coordinates outside valid geographic bounds")


def align_spatial_cell(latitude: float, longitude: float, lat_grid: np.ndarray, lon_grid: np.ndarray,
                       resolution: float, *, center_tolerance: float | None = None) -> tuple[int,int] | None:
    """Return containing canonical grid cell; outside points return None (no extrapolation)."""
    lat, lon = float(latitude), float(longitude)
    if not np.isfinite(lat) or not np.isfinite(lon): return None
    south, north = lat_grid[0]-resolution/2, lat_grid[-1]+resolution/2
    west, east = lon_grid[0]-resolution/2, lon_grid[-1]+resolution/2
    eps=1e-9
    if lat < south-eps or lat > north+eps or lon < west-eps or lon > east+eps: return None
    iy=min(len(lat_grid)-1,max(0,int(np.floor((lat-south)/resolution))))
    ix=min(len(lon_grid)-1,max(0,int(np.floor((lon-west)/resolution))))
    if center_tolerance is not None and (abs(lat-lat_grid[iy])>center_tolerance or abs(lon-lon_grid[ix])>center_tolerance): return None
    return iy,ix


def build_era5_grid(records: Iterable[dict], schema: dict, *, resolution: float = 0.5,
                    limits: PipelineLimits | None = None) -> dict[str, Any]:
    """Group decoded GRIB records into [time, channel, lat, lon], fail on gaps."""
    lat_grid, lon_grid, _ = _grid({**schema, "grid":{**schema["grid"], "canonical_resolution_degrees":resolution}})
    limits=limits or PipelineLimits()
    if len(lat_grid)*len(lon_grid)>limits.max_grid_cells: raise ValueError("configured grid exceeds MAX_GRID_CELLS")
    fields=[]
    for field in schema["sources"]["era5_single_levels"]["fields"]:
        fields.append((str(field["id"]),str(field["grib_short_name"]),None))
    for level in schema["sources"]["era5_pressure_levels"]["levels_hpa"]:
        for field in schema["sources"]["era5_pressure_levels"]["fields"]:
            fields.append((f"{field['id']}@{int(level)}hPa",str(field["grib_short_name"]),int(level)))
    names=[f[0] for f in fields]; lookup={(short,lev):i for i,(_,short,lev) in enumerate(fields)}
    grouped: dict[datetime,dict[int,np.ndarray]]={}; hashes=set(); source_files=set(); units={}
    record_count=0; point_count=0
    for rec in records:
        record_count+=1
        if record_count>limits.max_records_in_memory: raise ValueError("decoded input exceeds MAX_RECORDS_IN_MEMORY")
        short=str(rec["short_name"]); level=rec.get("level_hpa")
        key=(short,int(level) if level is not None else None)
        if key not in lookup: raise ValueError(f"unexpected ERA5 field {key}")
        stamp=_parse_time(rec["valid_time_utc"]); c=lookup[key]
        if c in grouped.setdefault(stamp,{}): raise ValueError(f"duplicate ERA5 field {key} at {stamp.isoformat()}")
        values=np.asarray(rec["values"],dtype=np.float64).reshape(-1)
        lats=np.asarray(rec["latitude"],dtype=np.float64).reshape(-1); lons=np.asarray(rec["longitude"],dtype=np.float64).reshape(-1)
        if not (values.size==lats.size==lons.size) or not np.isfinite(values).all() or not np.isfinite(lats).all() or not np.isfinite(lons).all():
            raise ValueError("ERA5 record has malformed/non-finite values or coordinates")
        _validate_source_coordinates(lats,lons); point_count+=values.size
        if point_count>limits.max_records_in_memory: raise ValueError("ERA5 points exceed MAX_RECORDS_IN_MEMORY")
        sums=np.zeros((len(lat_grid),len(lon_grid)),dtype=np.float64); counts=np.zeros_like(sums,dtype=np.uint16)
        for y,x,v in zip(lats,lons,values):
            cell=align_spatial_cell(y,x,lat_grid,lon_grid,resolution)
            if cell is not None: sums[cell]+=v; counts[cell]+=1
        if (counts==0).any(): raise IncompleteAtmosphericField(f"ERA5 field {key} at {stamp.isoformat()} does not cover every canonical cell")
        grouped[stamp][c]=(sums/counts).astype(np.float32)
        units[names[c]]=str(rec.get("units","")); hashes.add(str(rec.get("source_sha256",""))); source_files.add(str(rec.get("source_file","")))
    times=sorted(grouped)
    if not times: raise IncompleteAtmosphericField("no configured ERA5 fields were decoded")
    tensor=np.zeros((len(times),len(names),len(lat_grid),len(lon_grid)),dtype=np.float32); mask=np.zeros_like(tensor,dtype=bool)
    missing=[]
    for ti,t in enumerate(times):
        missing += [(t.isoformat(),names[c]) for c in range(len(names)) if c not in grouped[t]]
        for c,array in grouped[t].items(): tensor[ti,c]=array; mask[ti,c]=True
    return {"times":times,"tensor":tensor,"mask":mask,"latitude":lat_grid,"longitude":lon_grid,
            "feature_names":names,"units":units,"source_hashes":sorted(h for h in hashes if h),"source_files":sorted(f for f in source_files if f),"missing_fields":missing}


def _lis_datetime(tai_seconds: float, orbit_utc: str, tai_start: float) -> datetime:
    orbit=_parse_time(orbit_utc); epoch=datetime(1993,1,1,tzinfo=timezone.utc)
    offset=float(tai_start)-(orbit-epoch).total_seconds()
    return epoch+timedelta(seconds=float(tai_seconds)-offset)


def canonicalize_lis_records(decoded: dict) -> dict[str,Any]:
    """Expose source events and viewtime as timestamped provenance rows in UTC."""
    orbit=decoded.get("orbit_start_utc"); tai0=decoded.get("orbit_start_tai93")
    if not orbit or tai0 is None: raise ValueError("LIS needs orbit UTC and TAI93 start metadata for timestamp conversion")
    view=decoded["viewtime"]; events=decoded["events"]; digest=decoded["source_sha256"]; source=decoded["source_file"]
    coverage=[]
    for lat,lon,start,end,effective,flag in zip(view["lat"],view["lon"],view["TAI93_start"],view["TAI93_end"],view["effective_obs"],view["alert_flag"]):
        coverage.append({"timestamp_start":_lis_datetime(start,orbit,tai0),"timestamp_end":_lis_datetime(end,orbit,tai0),
            "latitude":float(lat),"longitude":float(lon),"effective_observation_seconds":float(effective),"quality_flag":int(flag),
            "coverage_observed":bool(float(effective)>0),"source_file":source,"source_hash":digest})
    event_rows=[]
    for lat,lon,timestamp,flag in zip(events["lat"],events["lon"],events["TAI93_time"],events["alert_flag"]):
        event_rows.append({"timestamp":_lis_datetime(timestamp,orbit,tai0),"latitude":float(lat),"longitude":float(lon),
            "event_observed":True,"quality_flag":int(flag),"source_file":source,"source_hash":digest})
    return {"viewtime":coverage,"events":event_rows,"source_file":source,"source_hash":digest}


def canonicalize_era5_records(decoded: dict) -> list[dict]:
    """Expand decoded field arrays into provenance-bearing canonical point records."""
    out=[]
    for r in decoded["records"]:
        for lat,lon,value in zip(r["latitude"],r["longitude"],r["values"]):
            out.append({"timestamp":r["valid_time_utc"],"latitude":float(lat),"longitude":float(lon),"variable":r.get("canonical_name"),
                        "short_name":r["short_name"],"level":r.get("level_hpa"),"value":float(value),"unit":r["units"],
                        "source_file":r["source_file"],"source_hash":r["source_sha256"]})
    return out


def build_lis_observation_grid(decoded: Iterable[dict], target_start: datetime, target_end: datetime,
                               latitude: np.ndarray, longitude: np.ndarray, resolution: float = 0.5,
                               *, policy: TargetPolicy | None = None) -> dict[str,Any]:
    """Build one target grid. Unknown remains masked; no-lightning requires full interval viewtime."""
    if target_end<=target_start: raise ValueError("target interval must be positive")
    if policy is None: raise TargetPolicyPending("TARGET_POLICY_STATUS=PENDING_APPROVAL")
    policy.validate()
    h,w=len(latitude),len(longitude); counts=np.zeros((h,w),dtype=np.uint32); intervals=[[[] for _ in range(w)] for _ in range(h)]
    source_hashes=set(); source_files=set(); quality_rejected=0; accepted_events=0
    for granule in decoded:
        source_hashes.add(granule.get("source_sha256","")); source_files.add(granule.get("source_file",""))
        orbit=granule.get("orbit_start_utc")
        tai_start=float(granule.get("orbit_start_tai93",0.0))
        v=granule["viewtime"]
        for lat,lon,a,b,flag in zip(v["lat"],v["lon"],v["TAI93_start"],v["TAI93_end"],v["alert_flag"]):
            if int(flag) not in policy.accepted_quality_flags: quality_rejected+=1; continue
            iyx=align_spatial_cell(lat,lon,latitude,longitude,resolution)
            if iyx is None: continue
            start=_lis_datetime(a,orbit,tai_start); end=_lis_datetime(b,orbit,tai_start)
            lo=max(start,target_start); hi=min(end,target_end)
            if hi>lo: intervals[iyx[0]][iyx[1]].append((lo,hi))
        e=granule["events"]
        for lat,lon,tai,flag in zip(e["lat"],e["lon"],e["TAI93_time"],e["alert_flag"]):
            if int(flag) not in policy.accepted_quality_flags: quality_rejected+=1; continue
            stamp=_lis_datetime(tai,orbit,tai_start)
            if not (target_start<=stamp<target_end): continue
            iyx=align_spatial_cell(lat,lon,latitude,longitude,resolution)
            if iyx is not None: counts[iyx]+=1; accepted_events+=1
    target=np.zeros((h,w),dtype=np.float32); observed=np.zeros((h,w),dtype=bool); quality=np.zeros((h,w),dtype=bool)
    full_coverage=0
    for iy in range(h):
        for ix in range(w):
            spans=sorted(intervals[iy][ix]); cursor=target_start
            for lo,hi in spans:
                if lo>cursor: break
                if hi>cursor: cursor=hi
                if cursor>=target_end: break
            continuous=cursor>=target_start+timedelta(seconds=(target_end-target_start).total_seconds()*policy.minimum_coverage_fraction)
            positive=counts[iy,ix]>0
            quality[iy,ix]=continuous or positive
            observed[iy,ix]=quality[iy,ix]
            if observed[iy,ix]: target[iy,ix]=float(positive)
            full_coverage+=int(continuous)
    return {"target":target,"observation_mask":observed,"quality_mask":quality,"event_count":counts,
            "coverage_metadata":{"target_start_utc":target_start.isoformat(),"target_end_utc":target_end.isoformat(),
                                 "full_interval_coverage_cells":full_coverage,"accepted_events":accepted_events,
                                 "rejected_quality_records":quality_rejected,"target_policy_version":policy.policy_version,
                                 "accepted_quality_flags":sorted(policy.accepted_quality_flags),
                                 "negative_definition":"continuous accepted viewtime spans the complete half-open target interval",
                                 "source_hashes":sorted(x for x in source_hashes if x),"source_files":sorted(x for x in source_files if x)}}


def align_features_to_prediction_time(era5: dict, prediction_time: datetime, sequence_length: int,
                                      cadence: timedelta=timedelta(hours=1), *, limits: PipelineLimits | None=None) -> tuple[np.ndarray,np.ndarray,list[datetime]]:
    """Exact causal history ending at T. Raises on any missing time/channel or future feature."""
    limits=limits or PipelineLimits()
    if sequence_length<1 or sequence_length>limits.max_sequence_length: raise ValueError("sequence_length outside configured MAX_SEQUENCE_LENGTH")
    needed=[prediction_time-cadence*(sequence_length-1-i) for i in range(sequence_length)]
    if max(needed)>prediction_time: raise DataLeakageError("feature timestamp exceeds prediction cutoff")
    index={t:i for i,t in enumerate(era5["times"])}
    if any(t not in index for t in needed): raise IncompleteAtmosphericField("required causal ERA5 input time is missing")
    X=era5["tensor"][[index[t] for t in needed]]; mask=era5["mask"][[index[t] for t in needed]]
    if not mask.all(): raise IncompleteAtmosphericField("required ERA5 input contains a missing configured field")
    if max(needed)>prediction_time: raise DataLeakageError("feature timestamp exceeds prediction cutoff")
    return X,mask,needed


def build_paired_dataset(era5_records: Iterable[dict], lis_granules: Iterable[dict], *, schema_path: str|Path,
                         sequence_length: int=4, forecast_horizon_steps: int=1,
                         resolution: float=0.5, dataset_version: str="strikecast-real-v1",
                         output_dir: str|Path|None=None, target_policy: TargetPolicy|None=None,
                         limits: PipelineLimits | None=None) -> CanonicalPairedDataset:
    schema=load_feature_schema(schema_path); limits=limits or PipelineLimits()
    era5=build_era5_grid(era5_records,schema,resolution=resolution,limits=limits)
    if sequence_length>limits.max_sequence_length: raise ValueError("sequence_length exceeds configured MAX_SEQUENCE_LENGTH")
    times=era5["times"]; samples=[]; candidate=0; missing_target=0
    by_hour={t:t for t in times}; lis_index=LISObservationIndex(lis_granules,era5["latitude"],era5["longitude"],resolution)
    if target_policy is None or not target_policy.approved:
        raise TargetPolicyPending("TARGET_POLICY_STATUS=PENDING_APPROVAL; real paired label generation is refused")
    cadence=timedelta(hours=float(schema["temporal"]["cadence_minutes"])/60)
    horizon=cadence*forecast_horizon_steps; target_duration=cadence
    for t in times:
        if any(t-cadence*i not in by_hour for i in range(sequence_length)): continue
        candidate+=1; target_start=t+horizon; target_end=target_start+target_duration
        X,fmask,input_times=align_features_to_prediction_time(era5,t,sequence_length,cadence)
        target_grid=build_lis_observation_grid(lis_index.granules_for(target_start,target_end),target_start,target_end,era5["latitude"],era5["longitude"],resolution,policy=target_policy)
        if not target_grid["observation_mask"].any(): missing_target+=1; continue
        sample_id=hashlib.sha256((dataset_version+"|"+t.isoformat()).encode()).hexdigest()[:24]
        hashes=sorted(set(era5["source_hashes"])|set(target_grid["coverage_metadata"]["source_hashes"]))
        samples.append({"sample_id":sample_id,"prediction_time":t,"feature_tensor":X,"target_tensor":target_grid["target"][None],
                        "target":target_grid["target"],"observation_mask":target_grid["observation_mask"],
                        "feature_mask":fmask,"latitude":era5["latitude"],"longitude":era5["longitude"],
                        "dataset_version":dataset_version,"source_hashes":hashes,"feature_schema_version":schema["schema_version"],
                        "target_schema_version":schema["target"]["schema_version"],"input_times":input_times,
                        "target_interval_utc":[target_start,target_end],"coverage_metadata":target_grid["coverage_metadata"]})
    manifest={"status":"READY" if samples else "BLOCKED_NO_DATA","dataset_version":dataset_version,
              "feature_schema_version":schema["schema_version"],"target_schema_version":schema["target"]["schema_version"],
              "feature_names":era5["feature_names"],"feature_units":era5["units"],"source_hashes":sorted(set(era5["source_hashes"])|{h for s in samples for h in s["source_hashes"]}),
              "source_files":era5["source_files"],"candidate_samples":candidate,"valid_samples":len(samples),"missing_features":len(era5["missing_fields"]),
              "missing_targets":missing_target,"prediction_cutoff":"all ERA5 times <= prediction_time",
              "target_interval_semantics":"[prediction_time + forecast_horizon, + one cadence)","target_unknown_policy":"mask false; unknown storage zero never enters loss"}
    if output_dir is not None and samples:
        _write_dataset(Path(output_dir),samples,era5,manifest)
    return CanonicalPairedDataset(samples,era5["latitude"],era5["longitude"],era5["feature_names"],schema["schema_version"],schema["target"]["schema_version"],manifest)


def split_and_normalize(dataset: CanonicalPairedDataset, *, train_fraction: float=.7,
                        validation_fraction: float=.15) -> dict[str,Any]:
    """Chronological whole-sample split with boundary embargo and train-only masked z-score."""
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction+validation_fraction>=1:
        raise ValueError("split fractions must be positive and leave a nonempty test fraction")
    samples=sorted(dataset.samples,key=lambda s:s["prediction_time"])
    if len(samples)<3: raise ValueError("at least three valid samples are required for train/validation/test")
    train_cut=samples[min(len(samples)-1,max(1,math.ceil(len(samples)*train_fraction)))]["prediction_time"]
    val_cut=samples[min(len(samples)-1,max(2,math.ceil(len(samples)*(train_fraction+validation_fraction))))]["prediction_time"]
    splits={"train":[],"validation":[],"test":[]}; dropped=0
    for s in samples:
        start=s["input_times"][0]; end=s["target_interval_utc"][1]
        if end<=train_cut and s["prediction_time"]<train_cut: name="train"
        elif start>=train_cut and end<=val_cut and s["prediction_time"]<val_cut: name="validation"
        elif start>=val_cut: name="test"
        else: dropped+=1; continue
        splits[name].append(s)
    if any(not splits[n] for n in splits): raise ValueError("chronological split leaves an empty split after whole-window embargo")
    c=len(dataset.feature_names); train_values=np.concatenate([s["feature_tensor"].transpose(0,2,3,1).reshape(-1,c) for s in splits["train"]],axis=0)
    train_masks=np.concatenate([s["feature_mask"].transpose(0,2,3,1).reshape(-1,c) for s in splits["train"]],axis=0)
    stats={}
    for i,name in enumerate(dataset.feature_names):
        values=train_values[train_masks[:,i],i]
        if values.size==0: raise ValueError(f"no observed training values for channel {name}")
        mean=float(values.mean()); std=max(float(values.std()),1e-6); stats[name]={"mean":mean,"std":std}
    normalized={}
    for split,rows in splits.items():
        normalized[split]=[]
        for s in rows:
            X=s["feature_tensor"].copy()
            for i,name in enumerate(dataset.feature_names): X[:,i]=(X[:,i]-stats[name]["mean"])/stats[name]["std"]
            X[~s["feature_mask"]]=0.0
            normalized[split].append({**s,"feature_tensor":X.astype(np.float32)})
    return {"splits":normalized,"normalization":{"method":"z_score","fit_split":"train","feature_stats":stats,
            "normalization_version":"train_only_zscore_v1",
            "feature_names":dataset.feature_names,"feature_schema_hash":hashlib.sha256(json.dumps(dataset.feature_names).encode()).hexdigest(),
            "dataset_version":dataset.manifest["dataset_version"]},
            "metadata":{"method":"chronological_whole_window_embargo_v1","train_end_utc":train_cut.isoformat(),
                        "validation_end_utc":val_cut.isoformat(),"dropped_boundary_samples":dropped,
                        "split_sample_counts":{k:len(v) for k,v in splits.items()}}}


def train_canonical_conv_lstm(dataset: CanonicalPairedDataset, *, training_config: dict,
                              output_root: str|Path, training_config_path: str|Path|None=None) -> dict[str,Any]:
    """Fit/evaluate/calibrate a masked grid ConvLSTM and validate a candidate artifact.

    This function never promotes production. Candidate creation is gated on
    nonempty chronological splits, class diversity, and a validation-fitted
    calibrator; fixtures may exercise the mechanics but never imply skill.
    """
    if not dataset.samples: return {"status":"BLOCKED_NO_DATA","counts":dataset.counts,"candidate":None}
    try: prepared=split_and_normalize(dataset,train_fraction=float(training_config.get("train_fraction",.7)),validation_fraction=float(training_config.get("validation_fraction",.15)))
    except ValueError as exc: return {"status":"BLOCKED_NO_DATA","reason":str(exc),"counts":dataset.counts,"candidate":None}
    labels={k:np.concatenate([s["target"][s["observation_mask"]].astype(np.int64) for s in v]) for k,v in prepared["splits"].items()}
    if any(not len(v) or set(np.unique(v))!={0,1} for v in labels.values()):
        return {"status":"BLOCKED_NO_DATA","reason":"each chronological split requires observed positive and negative targets","counts":dataset.counts,"candidate":None}
    import sys, torch
    root=Path(__file__).resolve().parents[3]
    sys.path[:0]=[str(root),str(root/"ml/research/strikecast")]
    from ml.training.strikecast_training.config import DataContract
    from src.models.convlstm import ConvLSTM
    from strikecast_core.evaluation.metrics import evaluate_binary_classifier
    from strikecast_core.security.model_registry import REQUIRED, validate_model_artifact
    from torch.utils.data import DataLoader, TensorDataset
    import torch.nn.functional as F
    seed=int(training_config.get("seed",42)); torch.manual_seed(seed); np.random.seed(seed)
    device=torch.device("cuda" if torch.cuda.is_available() and training_config.get("device","cpu")=="cuda" else "cpu")
    def tensors(split):
        rows=prepared["splits"][split]
        x=np.stack([s["feature_tensor"] for s in rows]).astype(np.float32)
        y=np.stack([s["target"][None,None] for s in rows]).astype(np.float32)
        m=np.stack([s["observation_mask"][None,None] for s in rows]).astype(bool)
        return torch.from_numpy(x),torch.from_numpy(y),torch.from_numpy(m)
    train_x,train_y,train_m=tensors("train"); val_x,val_y,val_m=tensors("validation"); test_x,test_y,test_m=tensors("test")
    batch_size=int(training_config.get("batch_size",16)); epochs=int(training_config.get("max_epochs",100))
    if batch_size<1 or epochs<1: raise ValueError("batch_size and max_epochs must be positive")
    contract=DataContract(sequence_length=train_x.shape[1],input_channels=train_x.shape[2],height=train_x.shape[3],width=train_x.shape[4],forecast_horizon=1,target_type="binary",input_channel_names=dataset.feature_names)
    hidden=list(training_config.get("conv_hidden_dims",[16,16])); kernel=int(training_config.get("conv_kernel_size",3))
    model=ConvLSTM(contract,hidden_dims=hidden,kernel_size=kernel).to(device)
    opt_name=str(training_config.get("optimizer","adam")).lower(); lr=float(training_config.get("learning_rate",1e-3))
    optimizer=torch.optim.Adam(model.parameters(),lr=lr) if opt_name=="adam" else torch.optim.SGD(model.parameters(),lr=lr)
    scheduler_name=str(training_config.get("scheduler","none")).lower()
    scheduler=(torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode="min",patience=int(training_config.get("scheduler_patience",5)),
              factor=float(training_config.get("scheduler_factor",.5)),min_lr=float(training_config.get("scheduler_min_learning_rate",1e-6)))
              if scheduler_name=="reduce_on_plateau" else None)
    if scheduler_name not in {"none","reduce_on_plateau"}: raise ValueError(f"unsupported scheduler: {scheduler_name}")
    train_loader=DataLoader(TensorDataset(train_x,train_y,train_m),batch_size=batch_size,shuffle=True,generator=torch.Generator().manual_seed(seed))
    val_loader=DataLoader(TensorDataset(val_x,val_y,val_m),batch_size=batch_size,shuffle=False)
    best=float("inf"); best_state=None; best_epoch=0; patience=int(training_config.get("early_stopping_patience",epochs)); stale=0; history=[]
    for epoch in range(epochs):
        model.train(); loss_sum=0.; observed_n=0
        for xb,yb,mb in train_loader:
            xb,yb,mb=xb.to(device),yb.to(device),mb.to(device)
            if not mb.any(): continue
            optimizer.zero_grad(set_to_none=True); probabilities=model(xb)
            loss=F.binary_cross_entropy(probabilities[mb],yb[mb]); loss.backward(); optimizer.step()
            loss_sum+=float(loss.detach())*int(mb.sum()); observed_n+=int(mb.sum())
        if not observed_n: return {"status":"BLOCKED_NO_DATA","reason":"training batches contain no observed target cells","counts":dataset.counts,"candidate":None}
        model.eval(); val_loss_sum=0.; val_n=0
        with torch.no_grad():
            for xb,yb,mb in val_loader:
                xb,yb,mb=xb.to(device),yb.to(device),mb.to(device)
                if mb.any(): val_loss_sum+=float(F.binary_cross_entropy(model(xb)[mb],yb[mb]))*int(mb.sum()); val_n+=int(mb.sum())
        val_loss=val_loss_sum/val_n if val_n else float("inf"); history.append({"epoch":epoch+1,"train_loss":loss_sum/observed_n,"validation_loss":val_loss})
        if scheduler is not None and np.isfinite(val_loss): scheduler.step(val_loss)
        if val_loss<best:
            best=val_loss; best_epoch=epoch+1; stale=0; best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        else: stale+=1
        if stale>=patience: break
    if best_state is None: return {"status":"BLOCKED_NO_DATA","reason":"validation did not produce a finite model-selection loss","counts":dataset.counts,"candidate":None}
    model.load_state_dict(best_state); model.eval()
    def predict(x):
        with torch.no_grad(): return torch.cat([model(xb.to(device)).cpu() for xb in DataLoader(x,batch_size=batch_size,shuffle=False)]).numpy()
    val_p=predict(val_x); test_p=predict(test_x)
    vy=val_y.numpy()[val_m.numpy()].astype(int); vp=val_p[val_m.numpy()]; ty=test_y.numpy()[test_m.numpy()].astype(int); tp=test_p[test_m.numpy()]
    if len(vy)<20: return {"status":"BLOCKED_NO_DATA","reason":"validation needs at least 20 observed targets for calibration","counts":dataset.counts,"candidate":None}
    from sklearn.linear_model import LogisticRegression
    logits=np.log(np.clip(vp,1e-6,1-1e-6)/(1-np.clip(vp,1e-6,1-1e-6)))
    calibrator=LogisticRegression(random_state=seed,solver="liblinear").fit(logits.reshape(-1,1),vy)
    test_logits=np.log(np.clip(tp,1e-6,1-1e-6)/(1-np.clip(tp,1e-6,1-1e-6)))
    calibrated=calibrator.predict_proba(test_logits.reshape(-1,1))[:,1]
    raw_metrics=evaluate_binary_classifier(ty.tolist(),tp.tolist()).to_dict()
    calibrated_metrics=evaluate_binary_classifier(ty.tolist(),calibrated.tolist()).to_dict()
    train_y_flat=labels["train"]; climatology=float(train_y_flat.mean())
    baseline={"climatology":evaluate_binary_classifier(ty.tolist(),[climatology]*len(ty)).to_dict()}
    scores=[]; truths=[]; eligible_samples=0; ineligible_samples=0
    history=dataset.samples
    for sample in prepared["splits"]["test"]:
        persistence=PersistenceBaseline.for_sample(sample,history)
        if persistence["status"]!="READY": ineligible_samples+=1; continue
        eligible_samples+=1; overlap=sample["observation_mask"] & persistence["observation_mask"]
        if overlap.any():
            scores.extend(persistence["target"][overlap].tolist()); truths.extend(sample["target"][overlap].astype(int).tolist())
        else: ineligible_samples+=1; eligible_samples-=1
    if scores and len(set(truths))==2:
        baseline["persistence"]={**evaluate_binary_classifier(truths,scores).to_dict(),"status":"READY",
                                  "eligible_samples":eligible_samples,"ineligible_samples":ineligible_samples}
    else:
        baseline["persistence"]={"status":"NOT_APPLICABLE","eligible_samples":eligible_samples,
                                  "ineligible_samples":ineligible_samples,
                                  "reason":"No valid prior-observation test population with both target classes."}
    try:
        from sklearn.linear_model import LogisticRegression as BaselineLogistic
        def flatten_cells(rows):
            features=[]; targets=[]
            for row in rows:
                _,channels,height,width=row["feature_tensor"].shape
                features.append(row["feature_tensor"].transpose(2,3,0,1).reshape(height*width,-1))
                targets.append(row["target"].reshape(-1));
            return np.concatenate(features),np.concatenate(targets)
        bx,by=flatten_cells(prepared["splits"]["train"]); tx,ty_all=flatten_cells(prepared["splits"]["test"])
        train_mask=np.concatenate([s["observation_mask"].reshape(-1) for s in prepared["splits"]["train"]])
        test_mask=np.concatenate([s["observation_mask"].reshape(-1) for s in prepared["splits"]["test"]])
        classic=BaselineLogistic(random_state=seed,max_iter=300,solver="liblinear").fit(bx[train_mask],by[train_mask].astype(int))
        baseline["classical_ml"]=evaluate_binary_classifier(ty_all[test_mask].astype(int).tolist(),classic.predict_proba(tx[test_mask])[:,1].tolist()).to_dict()
    except Exception as exc:
        baseline["classical_ml"]={"status":"NOT_COMPUTABLE","reason":f"classical baseline failed safely: {type(exc).__name__}: {exc}"}
    output=Path(output_root); version=f"{dataset.manifest['dataset_version']}-{hashlib.sha256((str(seed)+str(len(dataset.samples))).encode()).hexdigest()[:8]}"
    candidate=output/version
    if candidate.exists(): raise FileExistsError(f"candidate artifact already exists: {candidate}")
    candidate.mkdir(parents=True)
    torch.save(best_state,candidate/"model.pt")
    model_digest=hashlib.sha256((candidate/"model.pt").read_bytes()).hexdigest()
    feature_schema={"schema_version":dataset.feature_schema_version,"features":dataset.feature_names,"units":dataset.manifest.get("feature_units",{})}
    target_schema={"schema_version":dataset.target_schema_version,"unknown_policy":"masked and excluded","target_interval":dataset.manifest["target_interval_semantics"]}
    (candidate/"model_metadata.json").write_text(json.dumps({"model_version":version,"architecture":"StrikeCastConvLSTM","schema_version":dataset.feature_schema_version,"feature_schema_version":dataset.feature_schema_version,"served_feature_schema_version":SERVED_FEATURE_SCHEMA_VERSION,"normalization_version":"train_only_zscore_v1","dataset_version":dataset.manifest["dataset_version"],"model_input_shape":list(train_x.shape[1:]),"input_shape":list(train_x.shape[1:]),"target_shape":[1,1,train_x.shape[-2],train_x.shape[-1]],"best_epoch":best_epoch,"model_hash":model_digest,"inference_compatibility":"UNSUPPORTED"},indent=2)+"\n",encoding="utf-8")
    (candidate/"dataset_manifest.json").write_text(json.dumps(dataset.manifest,indent=2)+"\n",encoding="utf-8")
    (candidate/"feature_schema.json").write_text(json.dumps(feature_schema,indent=2)+"\n",encoding="utf-8")
    (candidate/"target_schema.json").write_text(json.dumps(target_schema,indent=2)+"\n",encoding="utf-8")
    norm=prepared["normalization"]
    (candidate/"normalization.json").write_text(json.dumps(norm,indent=2)+"\n",encoding="utf-8")
    cfg_text=Path(training_config_path).read_text(encoding="utf-8") if training_config_path else yaml.safe_dump(training_config)
    (candidate/"training_config.yaml").write_text(cfg_text,encoding="utf-8")
    is_fixture="fixture" in str(dataset.manifest["dataset_version"]).lower() or dataset.manifest.get("data_origin")=="TEST_FIXTURE"
    metrics={"status":"TEST_FIXTURE_MECHANICS_ONLY" if is_fixture else "MEASURED_ON_TEST","split":"test","raw":raw_metrics,"calibrated":calibrated_metrics,"baselines":baseline,"validation_loss_history":history,"population":"observed target-mask cells only"}
    (candidate/"metrics.json").write_text(json.dumps(metrics,indent=2,default=lambda value:value.isoformat() if isinstance(value,datetime) else str(value))+"\n",encoding="utf-8")
    cal={"method":"Platt scaling","fit_split":"validation","evaluation_split":"test","intercept":float(calibrator.intercept_[0]),"coefficient":float(calibrator.coef_[0][0]),"validation_population":int(len(vy)),"feature_schema_hash":norm["feature_schema_hash"],"model_hash":model_digest}
    (candidate/"calibration.json").write_text(json.dumps(cal,indent=2)+"\n",encoding="utf-8")
    card=(f"# StrikeCast model card\n\n- Purpose: grid lightning occurrence at configured one-hour horizon.\n- Features: {', '.join(dataset.feature_names)}.\n- Dataset: {dataset.manifest['dataset_version']}; samples: {len(dataset.samples)}.\n- Architecture: research ConvLSTM grid head; seed {seed}; epochs run {len(history)}.\n- Normalization: train-only z-score.\n- Metrics: test split only; see metrics.json.\n- Calibration: validation-only Platt scaling; see calibration.json.\n- Scientific validation: NOT ESTABLISHED; fixture metrics are mechanics-only.\n- Model version: {version}.\n")
    (candidate/"model_card.md").write_text(card,encoding="utf-8")
    checks=[]
    for name in sorted(REQUIRED-{"checksums.sha256"}):
        digest=hashlib.sha256((candidate/name).read_bytes()).hexdigest(); checks.append(f"{digest}  {name}")
    (candidate/"checksums.sha256").write_text("\n".join(checks)+"\n",encoding="utf-8")
    validated=validate_model_artifact(candidate,expected_schema_version=dataset.feature_schema_version,expected_dataset_version=dataset.manifest["dataset_version"])
    return {"status":"CANDIDATE_VALIDATED_NOT_PROMOTED","candidate":str(candidate),"registry_validation":validated,"metrics":metrics,"calibration":cal,"split_metadata":prepared["metadata"]}


def _write_dataset(root: Path, samples: list[dict], era5: dict, manifest: dict) -> None:
    root.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(root/"paired.npz",sample_ids=np.asarray([s["sample_id"] for s in samples]),
        prediction_times=np.asarray([s["prediction_time"].isoformat() for s in samples]),
        X=np.stack([s["feature_tensor"] for s in samples]),y=np.stack([s["target"] for s in samples]),
        observation_mask=np.stack([s["observation_mask"] for s in samples]),feature_mask=np.stack([s["feature_mask"] for s in samples]),
        latitudes=era5["latitude"],longitudes=era5["longitude"])
    import hashlib
    payload=root/"paired.npz"; manifest["payload"]={"file":payload.name,"sha256":hashlib.sha256(payload.read_bytes()).hexdigest()}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
