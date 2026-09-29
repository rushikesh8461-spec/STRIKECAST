# Reproducibility requirements

Every future training run must use a unique immutable run ID and record: repository commit (or explicitly unavailable), dataset manifest and source hashes, feature/target schema hashes, preprocessing and normalization hashes, model/training/evaluation configuration, seed, Python/PyTorch/dependency versions, hardware when available, run timestamp, split boundaries, sample counts, metrics, calibrator, and checkpoint digest.

The current checkout has no `.git` directory, so commit identity cannot be captured. Root Python requirements include unpinned ranges and no Python lockfile; the web app has `package-lock.json`. Existing research outputs are not valid run records. `configs/training/real_data.yaml` is a blocked template, not evidence of a completed run. Never overwrite prior run directories or the demo checkpoint.
