# Round 2 leakage audit

Status: **BLOCKED_NO_DATA**

Eligible datasets inspected: 0.

| Leakage control | Result |
|---|---|
| feature availability before issue time | NOT_RUN_NO_DATASET |
| future target excluded from features | NOT_RUN_NO_DATASET |
| normalization fit split train only | NOT_RUN_NO_DATASET |
| whole windows do not overlap splits | NOT_RUN_NO_DATASET |
| calibration and selection validation only | NOT_RUN_NO_DATASET |
| duplicate samples across splits | NOT_RUN_NO_DATASET |
| source timestamp cutoff | NOT_RUN_NO_DATASET |
| calibration samples excluded from test | NOT_RUN_NO_DATASET |

## Dataset results

- No eligible real dataset manifest was found; checks were not run.

This gate does not build data. A failure returns a nonzero exit code; no leakage finding is waived.

## Limitations

- A valid result proves contract invariants in the prepared arrays and manifest; it does not independently prove provider timestamps or source-record uniqueness.
- Raw ERA5/LIS pairing and source-level deduplication are not implemented as a canonical paired-data builder.
