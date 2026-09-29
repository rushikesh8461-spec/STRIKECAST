# M2 â€” served feature adapter

`point.py` converts the canonical DEMO observation sequence into the fixed tensor consumed by `packages/strikecast_core/models/inference.py`. The served path uses eight point-derived features and synthetic spatial offsets; it is not a verified gridded neighborhood.

The separate research preprocessing/feature pipeline lives under `ml/research/strikecast/src/preprocessing/` and `ml/research/strikecast/src/features/`. It builds a different multimodal gridded tensor and is not wired to serving.

See [feature engineering details](../../../docs/ml/FEATURE_ENGINEERING.md) and [architecture decisions](../../../docs/architecture/DECISIONS.md).
