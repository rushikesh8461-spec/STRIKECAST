# Probability calibration

Status: `NOT_VALIDATED`. The API serves raw model probability, leaves `calibrated_probability` null, and labels calibration as unvalidated. No candidate calibrator is registered or activated.

`scripts/ml/calibrate.py` fits Platt scaling on VALIDATION predictions only and reports raw versus calibrated Brier score, ECE, and reliability-bin values on the untouched TEST archive. It requires both files to carry explicit `split` labels, matching dataset/feature/target/split/model lineage, unique and disjoint sample IDs, aligned binary labels, finite probabilities, and both label classes. Validation needs at least 20 samples. The script records input checksums and fit parameters and marks its result `CANDIDATE_NOT_ACTIVATED`.

```powershell
python scripts/ml/calibrate.py --validation <validation-predictions.npz> --test <untouched-test-predictions.npz> --output artifacts/calibration/candidate.json
```

Caller-supplied lineage and IDs still need review against the dataset manifest and chronological split. The command is not evidence that a calibrator improves reliability on real observations. Test results are descriptive final evaluation only and must not prompt retuning; a change requires a new version and a new untouched test period. LIVE remains blocked until calibration is independently reviewed and accepted.
