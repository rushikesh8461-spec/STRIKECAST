"""
Sample/demo dataset generator (Phase 7).

Run as:
    python -m src.ingestion.demo_generator

Generates deterministic synthetic data for all four sources
(satellite, lightning, nwp, radar) and writes them, plus metadata sidecars
and a run-level manifest, into data/sample_demo/. This is what lets the
entire M1 -> M2 -> ... -> M6 pipeline run offline for the SIH demo.

Reproducibility: every adapter derives its RNG from the single
`sample_demo.random_seed` config value (with a small fixed per-source
offset so sources don't produce identical noise) — rerunning this script
with the same config always produces byte-identical output.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import load_config
from .contract import utc_now_iso
from .sources import SatelliteDataSource, LightningDataSource, NWPDataSource, RadarDataSource
from .storage import save_record


SOURCE_CLASSES = {
    "satellite": SatelliteDataSource,
    "lightning": LightningDataSource,
    "nwp": NWPDataSource,
    "radar": RadarDataSource,
}


def generate_all(config=None) -> dict:
    """Generate all four demo sources. Returns a manifest dict and also
    writes manifest.json into the sample_demo metadata/ directory."""
    if config is None:
        config = load_config()

    manifest = {
        "generated_at": utc_now_iso(),
        "config_grid": config.grid_spec_dict(),
        "config_demo_params": config.demo_dataset_params(),
        "sources": {},
    }

    for name, cls in SOURCE_CLASSES.items():
        adapter = cls(config=config, demo=True)
        record = adapter.get_record()
        out_dir = config.source_dir(name, demo=True)
        npz_path, json_path = save_record(record, out_dir)
        manifest["sources"][name] = {
            "source_id": record.source_id,
            "dataset_version": record.dataset_version,
            "quality_status": record.quality.quality_status.value if record.quality else None,
            "npz_path": str(npz_path.relative_to(config.data_root)),
            "json_path": str(json_path.relative_to(config.data_root)),
        }

    metadata_dir = config.sample_demo_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    manifest = generate_all()
    print(f"Sample demo data generated at {utc_now_iso()}")
    for name, info in manifest["sources"].items():
        print(f"  - {name}: {info['source_id']} [{info['quality_status']}] -> {info['npz_path']}")
    print("Manifest written to data/sample_demo/metadata/manifest.json")


if __name__ == "__main__":
    main()
