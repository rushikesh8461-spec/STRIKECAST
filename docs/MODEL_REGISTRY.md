# Model registry and promotion

Registry slots are `artifacts/models/demo/`, `candidate/`, and `production/`. The only approved runtime artifact is the pinned demo checkpoint. Candidate acceptance is blocked and production contains no checkpoint.

Before any candidate can load or promote, create an immutable run directory containing weights, metadata, dataset manifest, feature and target schema snapshots, normalization, training config, metrics, calibration, SHA-256 checksums and a human-readable limitations card. Record run ID, seed, software/runtime versions, hardware where available, source hashes, and exact config hashes. Never overwrite an existing run. A run without repository commit identity must record that limitation.

The runtime loader currently checks the exact demo path, digest, required metadata, safe `weights_only` deserialization, and strict state dict. Do not treat this as a generic candidate registry. Candidate selection must not be caller-controlled. Promotion requires every checklist item in `artifacts/models/candidate/acceptance.json` and `configs/evaluation/acceptance.yaml`; if any gate is incomplete, remain BLOCKED.

Rollback means redeploying a previously approved immutable artifact and its matching config, then verifying its recorded checksum and API inference contract. There is no production artifact to roll back to yet.
