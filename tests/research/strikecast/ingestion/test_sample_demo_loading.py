import json

from src.ingestion.demo_generator import generate_all
from src.ingestion.storage import load_record


def test_generate_all_produces_all_sources(config):
    manifest = generate_all(config)
    assert set(manifest["sources"].keys()) == {"satellite", "lightning", "nwp", "radar"}
    for name, info in manifest["sources"].items():
        assert info["quality_status"] in {"ok", "degraded", "failed"}


def test_manifest_file_written(config):
    generate_all(config)
    manifest_path = config.sample_demo_dir / "metadata" / "manifest.json"
    assert manifest_path.exists()
    with open(manifest_path) as f:
        manifest = json.load(f)
    assert "sources" in manifest


def test_loaded_record_matches_generated_shape(config):
    manifest = generate_all(config)
    npz_rel = manifest["sources"]["satellite"]["npz_path"]
    npz_path = config.data_root / npz_rel
    record = load_record(npz_path)
    demo_cfg = config.demo_dataset_params()
    assert len(record.timestamps) == demo_cfg["n_timestamps"]
    assert record.data.shape[0] == demo_cfg["n_timestamps"]
