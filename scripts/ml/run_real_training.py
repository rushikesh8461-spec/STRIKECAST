#!/usr/bin/env python
"""Fail-closed single command for the provenance-bearing real-data pipeline."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT / "configs/training/real_data.yaml")
    p.add_argument("--dataset", type=Path, default=ROOT / "data/processed/real")
    p.add_argument("--reuse-current-coverage", action="store_true", help="Use the last generated ERA5 coverage inventory")
    a = p.parse_args()
    if not a.config.is_file():
        print(json.dumps({"status":"ENVIRONMENT_FAILURE","reason":"training_config_missing"})); return 3
    planner = ROOT / "scripts/data/plan_required_era5.py"
    if not a.reuse_current_coverage:
        result = subprocess.run([sys.executable, str(planner)], cwd=ROOT, text=True, capture_output=True)
        if result.returncode:
            print(json.dumps({"status":"ENVIRONMENT_FAILURE","stage":"coverage","detail":result.stdout[-2000:]})); return 3
    manifest_path = ROOT / "data/manifests/era5_required_coverage.json"
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = int(m["requirements"]["required_hour_count"])
        available = int(m["available_hour_count"])
        missing = m.get("missing_hours_utc")
        if missing is None:
            missing = [h.get("timestamp_utc", f"{day['date']}T{h['utc_hour'][:2]}:00:00+00:00")
                       for day in m.get("missing", []) for h in day.get("hours", [])]
        invalid = m.get("invalid", [])
    except Exception as exc:
        print(json.dumps({"status":"ENVIRONMENT_FAILURE","stage":"coverage_manifest","reason":str(exc)})); return 3
    if required != available or missing or invalid:
        print(json.dumps({"status":"BLOCKED_NO_DATA","required_hours":required,"available_hours":available,
                          "missing_hours":missing,"missing_hour_count":len(missing),"invalid_hours":invalid,
                          "note":"No training, evaluation, calibration, or candidate registration was performed."}, indent=2)); return 2
    import yaml
    raw_config=yaml.safe_load(a.config.read_text(encoding="utf-8")) or {}
    target_policy=raw_config.get("target_policy",{})
    if target_policy.get("status")!="APPROVED" or not isinstance(target_policy.get("accepted_quality_flags"),list):
        print(json.dumps({"status":"BLOCKED_SCIENTIFIC_POLICY","target_policy_status":target_policy.get("status","PENDING_APPROVAL"),
                          "reason":"Real target generation requires a versioned, scientifically approved LIS quality and coverage policy."},indent=2)); return 2
    try:
        sys.path[:0]=[str(ROOT/"packages"),str(ROOT/"ml/research/strikecast")]
        from ml.research.strikecast.src.ingestion.provider_adapters import ERA5Provider,LISProvider
        from strikecast_core.data.real_pipeline import build_paired_dataset,train_canonical_conv_lstm,TargetPolicy,PipelineLimits
        # Decode only planner-validated atmospheric files and domain-intersecting
        # LIS granules; raw files remain read-only.
        limits=PipelineLimits.from_config(raw_config)
        records=[]; seen=set()
        for entry in m.get("files",[]):
            if entry.get("status")!="VALID" or entry.get("duplicate_content"): continue
            path=ROOT/entry["path"]
            if path.stat().st_size>limits.max_source_file_size: raise ValueError(f"source exceeds MAX_SOURCE_FILE_SIZE: {entry['path']}")
            decoded=ERA5Provider.decode(None,path)
            if decoded["source_sha256"]!=entry["sha256"]: raise ValueError(f"source changed since coverage scan: {entry['path']}")
            records.extend(decoded["records"])
            if len(records)>limits.max_records_in_memory: raise ValueError("decoded ERA5 input exceeds MAX_RECORDS_IN_MEMORY")
        lis_source=json.loads((ROOT/"data/database/manifests/era5_required_coverage.json").read_text(encoding="utf-8"))
        lis_granules=[]; lis_record_count=0
        for row in lis_source["lis_granules"]["granules"]:
            path=ROOT/"data/raw"/row["raw_relative_path"]
            if path.stat().st_size>limits.max_source_file_size: raise ValueError(f"source exceeds MAX_SOURCE_FILE_SIZE: {path.name}")
            decoded=LISProvider.decode(None,path)
            if decoded["source_sha256"]!=row["sha256"]: raise ValueError(f"LIS source changed since coverage scan: {path.name}")
            lis_record_count+=len(decoded["viewtime"]["lat"])+len(decoded["events"]["lat"])
            if lis_record_count>limits.max_lis_records_in_memory: raise ValueError("decoded LIS input exceeds MAX_LIS_RECORDS_IN_MEMORY")
            lis_granules.append(decoded)
        dataset_path=ROOT/"data/processed/real_canonical"
        policy=TargetPolicy(frozenset(int(v) for v in target_policy["accepted_quality_flags"]),str(target_policy.get("policy_version") or ""),
                            approved=True,minimum_coverage_fraction=float(target_policy.get("minimum_coverage_fraction",1.0)),
                            negative_label_rule=str(target_policy.get("negative_label_rule","")),viewtime_rule=str(target_policy.get("viewtime_rule","")))
        dataset=build_paired_dataset(records,lis_granules,schema_path=ROOT/"configs/data/feature_schema.yaml",
            sequence_length=int(raw_config.get("sequence_length",4)),
            forecast_horizon_steps=int(raw_config.get("forecast_horizon_steps",1)),
            resolution=float(raw_config.get("grid_resolution_degrees",.5)),dataset_version="strikecast-real-2023",output_dir=dataset_path,
            target_policy=policy,limits=limits)
        if not dataset.samples:
            print(json.dumps({"status":"BLOCKED_NO_DATA","counts":dataset.counts,"dataset_status":dataset.manifest["status"],
                              "reason":"No target intervals had defensible LIS observation coverage; unknown cells were not labeled negative."},indent=2)); return 2
        # Canonical raw samples and manifest are useful audit artifacts; split
        # tensors remain generated from these source-derived samples.
        train_cfg=raw_config.get("training",{})
        result=train_canonical_conv_lstm(dataset,training_config=train_cfg,
            output_root=ROOT/train_cfg.get("output_root","artifacts/models/candidate"),training_config_path=a.config)
        print(json.dumps(result,indent=2,default=str))
        return 0 if result.get("status")=="CANDIDATE_VALIDATED_NOT_PROMOTED" else 2
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED_INVALID_REAL_DATA","reason":f"{type(exc).__name__}: {exc}",
                          "note":"No candidate was promoted; check source metadata and LIS observation policy."},indent=2)); return 2

if __name__ == "__main__": raise SystemExit(main())
