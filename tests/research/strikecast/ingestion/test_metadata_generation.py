from src.ingestion.metadata import build_provenance
from src.ingestion.sources import SatelliteDataSource


def test_provenance_marks_synthetic_data_explicitly():
    prov = build_provenance("src1", "0.1.0", "synthetic_generator", is_synthetic=True)
    assert prov["is_synthetic"] is True
    assert "ingested_at" in prov
    assert prov["source_id"] == "src1"


def test_record_metadata_dict_has_required_fields(config):
    adapter = SatelliteDataSource(config=config, demo=True)
    record = adapter.get_record()
    meta = record.as_metadata_dict()
    for field in [
        "source", "source_id", "dataset_version", "n_timestamps",
        "timestamp_start", "timestamp_end", "grid", "variables",
        "quality", "provenance",
    ]:
        assert field in meta, f"missing required metadata field: {field}"
    assert meta["provenance"]["is_synthetic"] is True
