import pytest

from strikecast_core.risk.engine import RISK_THRESHOLDS, assess_risk, classify_risk


@pytest.mark.parametrize("name, expected", [("MODERATE", "MODERATE"), ("HIGH", "HIGH"), ("SEVERE", "SEVERE")])
def test_policy_threshold_epsilon_boundaries(name, expected):
    threshold = RISK_THRESHOLDS[name]
    assert classify_risk(threshold - 1e-9) != expected
    assert classify_risk(threshold) == expected
    assert classify_risk(threshold + 1e-9) == expected


def test_assessment_keeps_raw_probability_separate_from_calibration():
    assessment = assess_risk(0.61, 0.8, 60)
    assert assessment.probability == 0.61
    assert assessment.calibrated_probability is None
    assert assessment.risk_level == "HIGH"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, 1.01])
def test_invalid_probabilities_are_rejected(value):
    with pytest.raises(ValueError):
        classify_risk(value)
