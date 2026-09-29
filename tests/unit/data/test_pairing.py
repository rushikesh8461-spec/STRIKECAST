from packages.strikecast_core.alignment.pairing import build_pair_index


def test_missing_lis_coverage_is_unknown_and_never_negative():
    rows = build_pair_index(
        [{"timestamp_utc": "2023-11-16T01:00:00Z", "cell_id": "8.0,72.0",
          "available": True, "source_sha256": "a" * 64}], [],
        atmospheric_version="era5-v1", lightning_version="lis-v1")
    assert rows[0]["target_status"] == "UNKNOWN"
    assert rows[0]["quality_flags"] == ["NO_LIS_COVERAGE"]


def test_observed_lightning_and_observed_no_lightning_are_distinct():
    atmo = [{"timestamp_utc": "2023-11-16T01:00:00Z", "cell_id": "c",
             "available": True, "source_sha256": "a" * 64}]
    common = {"timestamp_utc": "2023-11-16T01:00:00Z", "cell_id": "c", "observed": True,
              "quality_flags": ["approved-by-adapter"], "source_sha256": "b" * 64}
    positive = build_pair_index(atmo, [{**common, "lightning_detected": True}],
                                atmospheric_version="e", lightning_version="l")
    negative = build_pair_index(atmo, [{**common, "lightning_detected": False}],
                                atmospheric_version="e", lightning_version="l")
    assert positive[0]["target_status"] == "POSITIVE"
    assert negative[0]["target_status"] == "NEGATIVE"
