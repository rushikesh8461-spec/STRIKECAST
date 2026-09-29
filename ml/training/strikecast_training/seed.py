"""
Single entry point for reproducibility. Call set_seed() at the start of
training and inference, before any model/data is created.
"""

import os
import random
import numpy as np
import torch


def set_seed(seed: int, deterministic: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)  # no-op if no CUDA
    os.environ["PYTHONHASHSEED"] = str(seed)

    if deterministic:
        # Trade some performance for determinism. Documented limitation:
        # certain CUDA ops (e.g. some atomics-based kernels) remain
        # non-deterministic even with these flags set — see PyTorch's
        # reproducibility notes. On CPU (this project's current default
        # device) these flags give exact determinism.
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def seed_worker(worker_id: int) -> None:
    """Pass as DataLoader(worker_init_fn=seed_worker) to also seed
    per-worker NumPy/random state deterministically when num_workers > 0."""
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)
