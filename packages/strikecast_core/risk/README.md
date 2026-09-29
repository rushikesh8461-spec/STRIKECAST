# M4 â€” served risk policy

`risk_engine.py` owns the API's risk transform and configurable, versioned thresholds. It reports raw probability separately from calibrated probability; calibrated probability is null and the policy is provisional because no held-out real labels or calibration evidence are available.

Evaluation and candidate calibration utilities do not activate a policy or establish model skill. See [risk policy](../../../docs/ml/RISK_POLICY.md), [evaluation](../../../docs/ml/EVALUATION.md), and [calibration](../../../docs/ml/CALIBRATION.md).
