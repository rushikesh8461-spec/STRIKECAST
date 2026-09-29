# M3 â€” served demo model

`inference.py` is the sole served model adapter. It loads `artifacts/models/demo/strikecast_convlstm_demo.pt` through pinned checksum/metadata checks and safe PyTorch loading. The ConvLSTM weights were trained on synthetic data; this artifact is **DEMO_ONLY** and has no real-data skill evidence. The explicit `demo/` directory distinguishes this runtime artifact from future candidate or production artifacts; those directories are not created until needed.

Research model definitions and inference experiments are in `ml/research/strikecast/src/models/` and related packages; training code is in `ml/training/strikecast_training/`. They are not production candidates and are not loaded by the API.

See [model feasibility](../../../docs/ml/MODEL_FEASIBILITY.md), [model card](../../../docs/ml/MODEL_CARD.md), and [checkpoint validation](../../../docs/reports/VERIFICATION_REPORT.md).
