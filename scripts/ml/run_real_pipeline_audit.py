#!/usr/bin/env python
"""Run the real-data training readiness gate; never trains or fabricates samples."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_PATH = ROOT / "data/database/manifests/era5_required_coverage.json"
INVENTORY_PATH = ROOT / "data/database/manifests/dataset_inventory.json"
REPORTS = ROOT / "artifacts/reports"


def main() -> int:
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    lis = coverage["lis_granules"]
    era5 = coverage["era5_request"]
    existing = era5["existing_required_hours_utc"]
    missing = era5["missing_required_hours_utc"]
    required_hours = sum(len(x["utc_hours"]) for x in era5["required_predictor_hours_utc"])
    existing_hours = sum(len(x["utc_hours"]) for x in existing)
    missing_hours = sum(len(x["utc_hours"]) for x in missing)
    paired_manifests = sorted((ROOT / "data/processed").rglob("manifest.json")) if (ROOT / "data/processed").exists() else []
    paired_manifests = [p for p in paired_manifests if "demo" not in p.parts and "research" not in p.parts]
    domain_rows = lis["granules"]
    nov16 = [row for row in domain_rows if row["orbit_id"] == 111326]
    exact_overlap = nov16[0] if nov16 else None
    generated = datetime.now(timezone.utc).isoformat()
    summary = {
        "generated_at_utc": generated,
        "data_status": "BLOCKED",
        "model_status": "DEMO_ONLY",
        "training_status": "BLOCKED_BEFORE_FIT",
        "evaluation_status": "NOT_RUN_NO_VALID_SAMPLES",
        "calibration_status": "NOT_RUN",
        "dataset_version": "NOT_CREATED_BLOCKED",
        "checkpoint": "artifacts/models/demo/strikecast_convlstm_demo.pt (unchanged)",
        "lis_readable_unique_granules": lis["readable_unique_granules_inspected"],
        "lis_domain_intersecting_granules": lis["domain_intersecting_granules"],
        "lis_non_intersecting_readable_granules": lis["non_intersecting_readable_granules"],
        "lis_domain_dates_utc": lis["domain_dates_utc"],
        "era5_required_predictor_hours": required_hours,
        "era5_existing_required_hours_both_products": existing_hours,
        "era5_missing_required_hours_both_products": missing_hours,
        "paired_real_dataset_manifests_found": len(paired_manifests),
        "split_counts": {
            split: {"samples": 0, "valid_samples": 0, "positive": "NOT_ENUMERATED_NO_SAMPLES",
                    "negative": "NOT_ENUMERATED_NO_SAMPLES", "unknown": "NOT_ENUMERATED_NO_SAMPLES"}
            for split in ("train", "validation", "test")
        },
        "leakage_audit": "BLOCKED_NO_REAL_PAIRED_SAMPLE_OR_AVAILABILITY_TIMELINE",
        "baseline_status": "NOT_RUN_NO_VALID_TRAIN_VALIDATION_SPLITS",
        "api_inference_status": "NO_REAL_CANDIDATE; DEMO CHECKPOINT/API CONTRACT ONLY",
        "overall_status": "BLOCKED_REAL_DATA_REQUIRED",
        "blockers": [
            f"Only {existing_hours} of {required_hours} required ERA5 predictor hours are currently present in both single- and pressure-level products; {missing_hours} are absent.",
            "The sole common-date domain pass has brief LIS view-time coverage (minutes, not a complete 60-minute target interval) and its rows carry alert flags requiring product-version review.",
            "No provenance-complete prepared real paired dataset manifest exists; unknown target cells cannot enter as negatives.",
            "Retrospective ERA5 analysis availability timestamps do not establish operational issue-time feature availability.",
        ],
        "additional_data_required": {
            "exact_era5_hours": missing,
            "all_era5_required_hours": era5["required_predictor_hours_utc"],
            "domain": coverage["domain"],
            "surface_variables": era5["surface_variables"],
            "pressure_variables": era5["pressure_variables"],
            "pressure_levels_hpa": era5["pressure_levels_hpa"],
            "label_coverage": "LIS target-interval view-time coverage and reviewed quality flags are required; ERA5 acquisition alone does not make unknown cells labelable.",
        },
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "TRAINING_INPUT_AUDIT.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    dates = lis["domain_dates_utc"]
    date_ranges = "2023-07-07–2023-07-31; 2023-09-26; 2023-09-28–2023-09-30; 2023-10-01–2023-11-16"
    exact_lis = "See `ERA5_REQUIRED_COVERAGE.md` and `era5_required_coverage.json` for every per-date view-time interval and every granule's source metadata, geolocation, event/flash timing, and quality flags."
    overlap_text = (
        f"Orbit {exact_overlap['orbit_id']} on 2023-11-16 has {exact_overlap['viewtime_records_in_domain']} view-time rows across "
        f"{exact_overlap['unique_viewtime_cells_in_domain']} cells, from {exact_overlap['viewtime_intervals_utc'][0][0]} through "
        f"{exact_overlap['viewtime_intervals_utc'][-1][1]}; {exact_overlap['flash_records_in_domain']} flashes and "
        f"{exact_overlap['event_records_in_domain']} events are within the domain for that pass."
        if exact_overlap else "No common-date LIS orbit metadata found."
    )

    (REPORTS / "TRAINING_INPUT_AUDIT.md").write_text(f"""# Training input audit

Status: **BLOCKED before sample construction/training**. Generated {generated} from the canonical inventory and the LIS-derived ERA5 requirement manifest.

```json
{json.dumps(summary, indent=2)}
```

## Source facts

- ERA5 archives: {len([r for r in inventory['files'] if r.get('category') == 'era5'])} canonical ERA5 ZIP paths are inventoried; separate single-level and pressure-level 2023 products cover 2023-11-16 00:00–23:00 UTC, and single levels additionally cover 2025-04-01–2025-12-31. No 2025 hours are used for 2023 LIS pairing.
- LIS: {lis['readable_unique_granules_inspected']} readable unique granules inspected; {lis['domain_intersecting_granules']} intersect N20/S8/W72/E82 and {lis['non_intersecting_readable_granules']} do not. Domain dates ({len(dates)}): {date_ranges}.
- Domain LIS totals: {lis['domain_viewtime_record_count']:,} view-time rows, {lis['domain_flash_record_count']:,} flashes, {lis['domain_event_record_count']:,} events. These counts are observations, not model samples.
- Required ERA5 history: {required_hours} distinct predictor hours; {existing_hours} are present in both products, {missing_hours} are missing. Per-date hour lists and required feature fields are in [`ERA5_REQUIRED_COVERAGE.md`](ERA5_REQUIRED_COVERAGE.md).
- {overlap_text}
- Complete per-granule all-collection audit: `era5_required_coverage.json` key `lis_granules.all_readable_granule_metadata_audit` (orbit bounds, geolocation bounds, view-time/event/flash bounds, counts and quality flags).
- Prepared real paired manifests found under data/processed (excluding demo/research fixtures): {len(paired_manifests)}.

## Compatibility and gate

The existing model consumes canonical tensors `[B,T,C,H,W]`; the present ConvLSTM does not reference ERA5/LIS filenames. The strict prepared-dataset loader validates lineage, feature availability times, spatial/temporal grid, chronology, train-only normalization and independent splits. This audit does not certify source-derived pairs because no such dataset exists. No raw provider pairing was fabricated or inferred from date overlap.
""", encoding="utf-8")

    (REPORTS / "TRAINING_DATASET_REPORT.md").write_text(f"""# Training dataset report

Status: **NO REAL DATASET CONSTRUCTED**. The strict paired NPZ contract was not satisfied: {len(paired_manifests)} provenance-complete real dataset manifests were found. The existing `data/processed/research/` arrays are research/demo preprocessing outputs and are not promoted or called real data.

The ERA5 request has {required_hours} hourly predictor timestamps ({existing_hours} present in both products, {missing_hours} missing). Data outside this exact request was not processed. An ERA5 time match cannot create a lightning label: LIS view-time must cover a complete target interval under reviewed quality policy. The only date with both ERA5 products has a sparse domain pass; other domain dates do not have both products.

No canonical samples were built. Counts of POSITIVE/NEGATIVE/UNKNOWN labels by split are therefore **not enumerated**, rather than treating unobserved cells as negatives. On the common-date overpass, 525 nominal cells remain unknown as recorded in the source audit. Dataset version: `NOT_CREATED_BLOCKED`.
""", encoding="utf-8")

    split_rows = "\n".join(f"| {s} | 0 | 0 | NOT ENUMERATED | NOT ENUMERATED | NOT ENUMERATED |" for s in ("train", "validation", "test"))
    (REPORTS / "TRAINING_SPLIT_REPORT.md").write_text(f"""# Training split report

Status: **NOT CREATED**. No valid paired samples exist to split. Configured split fractions are not applied to source granules or dates; doing so would misrepresent partial satellite passes as continuous samples.

| Split | Total samples | Valid samples | Positive | Negative | Unknown |
|---|---:|---:|---:|---:|---:|
{split_rows}

No train, validation, or test timestamps were allocated. Chronological boundaries and embargo are therefore not computable. The existing whole-window chronological splitter remains the intended implementation once a valid paired dataset is available; it assigns a complete input+target window to one split and drops boundary-crossing windows.
""", encoding="utf-8")

    (REPORTS / "TRAINING_RUN_REPORT.md").write_text(f"""# Training run report

Status: **BLOCKED BEFORE FIT**. The data gate found {required_hours} required ERA5 input hours, of which {missing_hours} are missing, and no prepared real paired dataset. There are no train windows with validated observation masks.

- Training executed: **NO**.
- Model/checkpoint: no candidate created; existing demo checkpoint was not modified.
- Training/validation loss, learning-rate history, class weighting, early stopping, and resume state: **NOT RUN**.
- Dataset version: `NOT_CREATED_BLOCKED`.
- Random seed: no fit occurred.

Exact missing ERA5 dates/hours and variables are listed in `ERA5_REQUIRED_COVERAGE.md` and `era5_required_coverage.json`. Satisfying ERA5 coverage alone is not sufficient: acquire/verify LIS observation coverage for complete target intervals and construct target observation masks before training.
""", encoding="utf-8")

    (REPORTS / "MODEL_COMPARISON.md").write_text(f"""# Model comparison

Status: **NOT RUN — NO VALID REAL SPLITS**. Climatology, persistence, classical baselines, and ConvLSTM must use the same observed-target mask and chronological test split. Neither exists for the current uploads. No validation winner or test metric was selected. The currently served model remains `DEMO_ONLY`.

The existing validation baseline runner now passes target masks to baselines and evaluates only observed validation cells. It must not be invoked until the strict real dataset contract passes.
""", encoding="utf-8")

    (REPORTS / "FINAL_MODEL_EVALUATION.md").write_text("""# Final model evaluation

Status: **NOT RUN — no valid real-data samples or held-out split**. The real-data pipeline stopped before fitting. There is no TEST prediction archive.

| Metric | Result |
|---|---|
| Confusion matrix, precision, recall, F1, CSI, POD, FAR | NOT COMPUTABLE — no test labels |
| ROC-AUC, PR-AUC | NOT COMPUTABLE — no test labels or class diversity |
| Brier score, reliability/calibration | NOT COMPUTABLE — no test probabilities |
| Held-out sample count | 0 |
| Calibration | NOT FIT |
| Model acceptance | BLOCKED |

These are unavailable metrics, not zero performance. No scientific forecast-skill conclusion is supported.
""", encoding="utf-8")

    (REPORTS / "MODEL_ACCEPTANCE_REPORT.md").write_text("""# Model acceptance report

**MODEL_STATUS: BLOCKED / DEMO_ONLY**

No candidate was created or promoted. Required dataset, target-mask, train/validation/test, observed class-diversity, baseline, untouched evaluation, calibration, and candidate inference gates remain unmet. The existing `artifacts/models/candidate/acceptance.json` remains BLOCKED; the demo checkpoint is unchanged.

Production/live acceptance requires a provenance-complete real dataset, approved LIS observation/quality semantics, causal/available features, non-empty chronological splits with valid class diversity, train-only normalization, masked loss, baseline comparison, final untouched test evaluation, calibration review, artifact integrity, reproducibility, and inference compatibility.
""", encoding="utf-8")

    print(json.dumps({"status": summary["overall_status"], "train": 0, "validation": 0, "test": 0,
                      "required_era5_hours": required_hours, "missing_era5_hours": missing_hours,
                      "reports": 7}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
