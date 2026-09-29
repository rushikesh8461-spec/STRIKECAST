from src.ingestion.validation.temporal import validate_temporal


def test_valid_hourly_sequence():
    ts = [f"2026-06-01T{h:02d}:00:00Z" for h in range(5)]
    result = validate_temporal(ts, expected_timestep_minutes=60)
    assert result["valid"] is True
    assert result["n_duplicates"] == 0
    assert result["is_chronological"] is True
    assert result["gaps"] == []
    assert result["coverage_fraction"] == 1.0


def test_detects_duplicates():
    ts = ["2026-06-01T00:00:00Z", "2026-06-01T00:00:00Z", "2026-06-01T02:00:00Z"]
    result = validate_temporal(ts, expected_timestep_minutes=60)
    assert result["n_duplicates"] == 1
    assert result["valid"] is False
    assert any("duplicate" in issue.lower() for issue in result["issues"])


def test_detects_non_chronological_order():
    ts = ["2026-06-01T02:00:00Z", "2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"]
    result = validate_temporal(ts)
    assert result["is_chronological"] is False
    assert result["valid"] is False


def test_detects_unexpected_gap():
    ts = ["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z", "2026-06-01T05:00:00Z"]
    result = validate_temporal(ts, expected_timestep_minutes=60)
    assert len(result["gaps"]) == 1
    assert result["coverage_fraction"] < 1.0


def test_rejects_naive_timestamp_without_timezone():
    ts = ["2026-06-01T00:00:00"]  # no Z / offset
    result = validate_temporal(ts)
    assert result["valid"] is False
    assert result["issues"]
