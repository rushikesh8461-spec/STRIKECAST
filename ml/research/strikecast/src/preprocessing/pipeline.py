"""
M2 pipeline CLI — runs the full temporal alignment -> spatial alignment ->
missing-data handling -> normalization -> feature engineering -> sequence/
target construction -> leakage-safe split, and persists the resulting
model-ready dataset + reproducibility metadata to data/processed/.

Run as:
    python -m src.preprocessing.pipeline

Mirrors src/ingestion/demo_generator.py's CLI style/conventions.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import load_config
from .dataset import build_dataset
from .normalization import save_normalization_stats


def _save_split(name: str, ds, out_dir: Path) -> dict:
    """Persist one split's windows as a single .npz (X, y, mask stacked
    across windows) — simple and dependency-free (Phase 5 note applied
    here too: no unnecessary format/abstraction for MVP data volumes)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(ds)
    if n == 0:
        path = out_dir / f"{name}.npz"
        np.savez_compressed(path, X=np.array([]), y=np.array([]), mask=np.array([]))
        return {"path": path.name, "n_windows": 0}

    samples = [ds[i] for i in range(n)]
    X = np.stack([s["X"] for s in samples], axis=0)      # [N, L, lat, lon, C]
    y = np.stack([s["y"] for s in samples], axis=0)       # [N, H, lat, lon]
    mask = np.stack([s["mask"] for s in samples], axis=0)  # [N, L, lat, lon, C]

    path = out_dir / f"{name}.npz"
    np.savez_compressed(path, X=X, y=y, mask=mask)
    return {"path": path.name, "n_windows": n, "X_shape": list(X.shape), "y_shape": list(y.shape)}


def run(config=None, demo: bool = True) -> dict:
    if config is None:
        config = load_config()

    bundle = build_dataset(config, demo=demo)

    out_dir = config.processed_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    split_info = {
        name: _save_split(name, ds, out_dir) for name, ds in bundle.splits.items()
    }

    norm_path = out_dir / config.normalization_cfg()["stats_filename"]
    save_normalization_stats(bundle.normalization_stats, norm_path)

    metadata = dict(bundle.metadata)
    metadata["channel_names"] = bundle.channel_names
    metadata["feature_schema"] = next(iter(bundle.splits.values())).get_feature_schema() if bundle.splits else []
    metadata["target_schema"] = next(iter(bundle.splits.values())).get_target_schema() if bundle.splits else {}
    metadata["splits"] = split_info
    # Metadata travels with the processed dataset; keep paths portable and
    # relative to dataset_metadata.json rather than embedding the build host.
    metadata["normalization_stats_path"] = norm_path.name

    metadata_path = out_dir / "dataset_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main():
    metadata = run()
    print(f"M2 model-ready dataset written to {Path(metadata['normalization_stats_path']).parent or '.'}/")
    for name, info in metadata["splits"].items():
        print(f"  - {name}: {info['n_windows']} window(s) -> {info['path']}")
    if metadata["warnings"]:
        print("Warnings:")
        for w in metadata["warnings"]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
