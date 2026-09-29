#!/usr/bin/env python
"""Run focused StrikeCast audit/data/train/evaluate/verify stages."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    for mode in ("audit","data","train","evaluate","verify","all"): group.add_argument("--"+mode,action="store_true")
    p.add_argument("--reuse-current-coverage",action="store_true")
    a=p.parse_args(); mode=next(k for k in ("audit","data","train","evaluate","verify","all") if getattr(a,k))
    stages={"audit":["scripts/ml/run_real_pipeline_audit.py"],"data":["scripts/data/plan_required_era5.py","scripts/ml/run_real_pipeline_audit.py"],
            "train":["scripts/ml/run_real_training.py"],"evaluate":["scripts/ml/evaluate.py"],
            "verify":["scripts/verification/run_round2_verification.py"],
            "all":["scripts/ml/run_real_pipeline_audit.py","scripts/data/plan_required_era5.py","scripts/ml/run_real_training.py","scripts/verification/run_round2_verification.py"]}[mode]
    blocked = False
    for stage in stages:
        cmd=[sys.executable,str(ROOT/stage)]
        if stage.endswith("run_real_training.py") and (a.reuse_current_coverage or mode=="all"): cmd.append("--reuse-current-coverage")
        if stage.endswith("run_round2_verification.py") and mode=="all": cmd.append("--reuse-current-era5-inventory")
        r=subprocess.run(cmd,cwd=ROOT)
        if r.returncode:
            if mode == "all" and stage.endswith("run_real_training.py") and r.returncode == 2:
                blocked = True
                continue
            return r.returncode
    if blocked:
        print(json.dumps({"status":"BLOCKED_NO_DATA","mode":mode,"note":"verification completed; no model stages ran"}))
        return 0
    print(json.dumps({"status":"PASS","mode":mode})); return 0
if __name__=="__main__": raise SystemExit(main())
