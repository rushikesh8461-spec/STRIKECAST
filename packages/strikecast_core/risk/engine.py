from __future__ import annotations
from dataclasses import dataclass
import math
import os

RISK_POLICY_VERSION = os.getenv("RISK_POLICY_VERSION", "provisional-1")
RISK_THRESHOLDS = {
    "MODERATE": float(os.getenv("RISK_MODERATE_THRESHOLD", "0.35")),
    "HIGH": float(os.getenv("RISK_HIGH_THRESHOLD", "0.60")),
    "SEVERE": float(os.getenv("RISK_SEVERE_THRESHOLD", "0.80")),
}
if not (0 < RISK_THRESHOLDS["MODERATE"] < RISK_THRESHOLDS["HIGH"] < RISK_THRESHOLDS["SEVERE"] < 1):
    raise RuntimeError("Risk thresholds must satisfy 0 < moderate < high < severe < 1")

@dataclass(frozen=True)
class RiskAssessment:
 probability: float; calibrated_probability: float | None; confidence: float; risk_level: str; forecast: str; alerts: list[str]
def classify_risk(p:float)->str:
 if not math.isfinite(float(p)) or not 0 <= p <= 1: raise ValueError("risk probability must be finite and within [0, 1]")
 return "SEVERE" if p>=RISK_THRESHOLDS["SEVERE"] else "HIGH" if p>=RISK_THRESHOLDS["HIGH"] else "MODERATE" if p>=RISK_THRESHOLDS["MODERATE"] else "LOW"
def assess_risk(raw_probability,raw_confidence,horizon_minutes):
 p=float(raw_probability); raw_confidence=float(raw_confidence)
 if not math.isfinite(p) or not 0 <= p <= 1: raise ValueError("raw probability must be finite and within [0, 1]")
 if not math.isfinite(raw_confidence) or not 0 <= raw_confidence <= 1: raise ValueError("raw confidence must be finite and within [0, 1]")
 if not 1 <= int(horizon_minutes) <= 1440: raise ValueError("horizon_minutes must be within [1, 1440]")
 level=classify_risk(p); conf=round(raw_confidence,4)
 forecast={"LOW":f"Low convective risk forecast for the next {horizon_minutes} minutes (probability={p:.2f}).","MODERATE":f"Moderate risk forecast for the next {horizon_minutes} minutes (probability={p:.2f}).","HIGH":f"High risk forecast for the next {horizon_minutes} minutes (probability={p:.2f}).","SEVERE":f"Severe risk forecast for the next {horizon_minutes} minutes (probability={p:.2f})."}[level]
 alerts={"LOW":[],"MODERATE":[f"Conditions may develop within {horizon_minutes} minutes; monitor updates."],"HIGH":[f"Elevated convective risk expected within {horizon_minutes} minutes; review local alerts."],"SEVERE":[f"Severe convective risk signal within {horizon_minutes} minutes; follow official safety guidance."]}[level]
 return RiskAssessment(round(p,4),None,conf,level,forecast,alerts)
