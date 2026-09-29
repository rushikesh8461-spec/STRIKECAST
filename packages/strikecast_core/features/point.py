from __future__ import annotations
from dataclasses import dataclass
from .served_schema import SERVED_FEATURE_NAMES, SERVED_FEATURE_RANGES

FEATURE_NAMES = list(SERVED_FEATURE_NAMES)
RANGES = SERVED_FEATURE_RANGES
@dataclass(frozen=True)
class FeatureBatch:
    feature_names: tuple[str,...]
    vector: tuple[float,...]
    sequence: tuple[tuple[tuple[float,...],...],...]
    data_source: str

def _norm(name,v):
    lo,hi=RANGES[name]; v=max(lo,min(hi,float(v))); return (v-lo)/(hi-lo)

def build_features(observations) -> FeatureBatch:
    if len(observations)<6: raise ValueError("At least 6 observations are required")
    rows=[]
    for obs in observations[-6:]:
        vec=tuple(_norm(name,getattr(obs,name)) for name in FEATURE_NAMES)
        # 3x3 spatial grid; small deterministic perturbation keeps the tensor spatial.
        grid=[]
        for r in range(3):
            row=[]
            for c in range(3):
                delta=(r-1)*0.004+(c-1)*0.003
                row.append(tuple(max(0,min(1,x+delta)) for x in vec))
            grid.append(tuple(row))
        rows.append(tuple(grid))
    latest=tuple(_norm(name,getattr(observations[-1],name)) for name in FEATURE_NAMES)
    return FeatureBatch(tuple(FEATURE_NAMES), latest, tuple(rows), observations[-1].source)
