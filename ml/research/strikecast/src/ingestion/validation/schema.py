"""Schema validation (Phase 6): expected variables, dims, dtype, valid ranges."""

from __future__ import annotations

import numpy as np

from ..contract import VariableSpec


def validate_schema(
    data: np.ndarray,
    variables: list[VariableSpec],
    expected_shape_prefix: tuple | None = None,
) -> dict:
    """
    Checks that `data`'s last axis matches len(variables), that dtype is
    float-like, and per-variable valid_min/valid_max ranges (ignoring NaN).

    `expected_shape_prefix`, if given, is compared against data.shape[:-1]
    (e.g. (n_time, n_lat, n_lon)).

    Returns dict: valid, issues, per_variable (dict[name -> {valid_fraction}])
    """
    issues: list[str] = []
    per_variable: dict[str, dict] = {}

    if data.ndim < 2:
        issues.append(f"Data array has too few dimensions: {data.shape}")
        return {"valid": False, "issues": issues, "per_variable": per_variable}

    n_vars_in_data = data.shape[-1]
    if n_vars_in_data != len(variables):
        issues.append(
            f"Variable count mismatch: data has {n_vars_in_data} channels, "
            f"schema declares {len(variables)} variables."
        )

    if expected_shape_prefix is not None and data.shape[:-1] != tuple(expected_shape_prefix):
        issues.append(
            f"Shape mismatch: expected leading dims {expected_shape_prefix}, "
            f"got {data.shape[:-1]}."
        )

    if not np.issubdtype(data.dtype, np.floating):
        issues.append(f"Data dtype {data.dtype} is not floating-point.")

    n_checkable = min(n_vars_in_data, len(variables))
    for i in range(n_checkable):
        var = variables[i]
        channel = data[..., i]
        finite_mask = np.isfinite(channel)
        n_finite = int(np.sum(finite_mask))
        if n_finite == 0:
            per_variable[var.name] = {"valid_fraction": 0.0}
            issues.append(f"Variable '{var.name}' has no finite values.")
            continue
        finite_vals = channel[finite_mask]
        in_range = np.ones_like(finite_vals, dtype=bool)
        if var.valid_min is not None:
            in_range &= finite_vals >= var.valid_min
        if var.valid_max is not None:
            in_range &= finite_vals <= var.valid_max
        valid_fraction = float(np.sum(in_range)) / float(finite_vals.size)
        per_variable[var.name] = {"valid_fraction": valid_fraction}
        if valid_fraction < 1.0:
            n_bad = int(finite_vals.size - np.sum(in_range))
            issues.append(
                f"Variable '{var.name}' has {n_bad} value(s) outside "
                f"[{var.valid_min}, {var.valid_max}]."
            )

    valid = not issues
    return {"valid": valid, "issues": issues, "per_variable": per_variable}
