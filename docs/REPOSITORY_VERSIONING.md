# Repository versioning and reproducibility

This checkout currently has no Git metadata. No commit, branch, or clean-tree claim can be made. Initialize version control from the repository root before recording a release; do not add raw/private data, credentials, virtual environments, caches, model outputs, or build directories.

## Dataset and model versions

Every accepted dataset must carry its own immutable `dataset_version`, provider manifests, timestamps, and SHA-256 payload checksum. Candidate models must be stored in a versioned registry directory and validated against their required checksums and schemas before explicit promotion. The production registry pointer is separate from the candidate and demo directories; promotion and rollback are operator actions.

## Reproducible runs

Record the config, seed, dataset version/checksum, feature and target schema versions, code revision (when Git becomes available), Python/runtime versions, metrics, calibration metadata, and artifact checksums with each run. Dependency auditing is separate from installation; registry access failures remain `UNAVAILABLE` and TLS verification must stay enabled. The web application has an npm lockfile. Python dependency inputs are not yet a complete hash-locked environment, so exact environment reproduction remains incomplete.

## Generated outputs

Verification reports belong under `artifacts/reports`; build products, caches, local environments, credentials, and generated data are ignored by `.gitignore`. Raw source data remains user-owned and must not be removed by repository cleanup.
