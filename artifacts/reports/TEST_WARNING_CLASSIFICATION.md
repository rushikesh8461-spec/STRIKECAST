# Test warning classification

Latest full Python run: 377 passed, 7 warnings.

| Count | Classification | Source | Action |
|---:|---|---|---|
| 1 | THIRD_PARTY | Starlette test client uses AnyIO's deprecated `BlockingPortal` alias. | No repository call site controls this alias; retain warning until the dependency updates. |
| 6 | THIRD_PARTY | Existing scikit-learn logistic-regression research tests trigger SciPy L-BFGS-B `disp`/`iprint` deprecation warnings. | Warnings originate inside installed dependencies; do not suppress them globally. |

No repository-owned actionable warnings were reported by this run.
