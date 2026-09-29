"""
Training entrypoint.

    python -m ml.training.strikecast_training.train --model convlstm --epochs 5
    python -m ml.training.strikecast_training.train --config configs/convlstm_default.yaml

Model-agnostic for the gradient-trained models (convlstm, fusion_convlstm).
persistence has no training step; classical_ml is fit via a separate path
(model.fit(x, y) called once over the full training set — see
train_classical() below) rather than the epoch loop, since sklearn
estimators aren't trained via SGD mini-batches here.
"""

import argparse
import dataclasses
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

import torch
import yaml
from torch.utils.data import DataLoader, random_split

from ml.training.strikecast_training.config import Config, DataContract, TrainConfig
from ml.training.strikecast_training.dataset import SyntheticDataset
from ml.training.strikecast_training.seed import set_seed, seed_worker
from ml.training.strikecast_training.losses import get_loss
from ml.training.strikecast_training.checkpoint import save_checkpoint
from src.models.factory import build_model


def load_config(path: Optional[str]) -> Config:
    if path is None:
        return Config()
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}
    data_cfg = DataContract(**raw.get("data", {}))
    train_cfg = TrainConfig(**raw.get("train", {}))
    return Config(data=data_cfg, train=train_cfg)


def build_dataloaders(config: Config, model_name: str = None):
    """
    Dispatches on config.train.data_source:
      - "synthetic": random tensors matching config.data exactly (unchanged
        behavior — shape/plumbing smoke tests, no real M2 dependency).
      - "m2": real windows from src.preprocessing.dataset.build_dataset().
        config.data is REPLACED in place with a contract derived from the
        loaded bundle (DataContract.from_m2_bundle) before the loaders are
        built, since the real grid/channel/target shapes are only known
        once M2 has actually run — see src/training/m2_bridge.py.

    Returns (train_loader, val_loader). val_loader may be None when the M2
    split has 0 windows (a documented possibility on small/demo data — see
    docs/m2_m3_contract.md "Known limitation"); callers must handle that.
    """
    if config.train.data_source == "m2":
        return _build_dataloaders_m2(config, model_name)

    full_dataset = SyntheticDataset(config.data, num_samples=32, seed=config.train.seed)
    val_size = max(1, len(full_dataset) // 5)
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(config.train.seed),
    )

    kwargs = dict(batch_size=config.train.batch_size, num_workers=config.train.num_workers)
    if config.train.num_workers > 0:
        kwargs["worker_init_fn"] = seed_worker

    train_loader = DataLoader(train_ds, shuffle=True, **kwargs)
    val_loader = DataLoader(val_ds, shuffle=False, **kwargs)
    return train_loader, val_loader


def _build_dataloaders_m2(config: Config, model_name: str):
    from ml.training.strikecast_training.m2_bridge import build_m2_dataset, load_m2_bundle

    multimodal = model_name == "fusion_convlstm"
    bundle = load_m2_bundle(config.train.m2_preprocessing_config, demo=config.train.m2_demo)
    config.data = DataContract.from_m2_bundle(bundle, multimodal=multimodal)

    for w in bundle.metadata.get("warnings", []):
        print(f"[m2 data] warning: {w}")

    kwargs = dict(batch_size=config.train.batch_size, num_workers=config.train.num_workers)
    if config.train.num_workers > 0:
        kwargs["worker_init_fn"] = seed_worker

    train_split = bundle.splits["train"]
    if len(train_split) == 0:
        raise ValueError(
            "M2's train split has 0 windows for the current preprocessing "
            "config — nothing to train on. See docs/m2_m3_contract.md "
            "'Known limitation' (e.g. bump sample_demo.n_timestamps)."
        )
    train_ds = build_m2_dataset(train_split, config.data, multimodal)
    train_loader = DataLoader(train_ds, shuffle=True, **kwargs)

    val_split = bundle.splits["val"]
    if len(val_split) == 0:
        print(
            "[m2 data] warning: val split has 0 windows — skipping validation "
            "this run (see docs/m2_m3_contract.md 'Known limitation')."
        )
        val_loader = None
    else:
        val_ds = build_m2_dataset(val_split, config.data, multimodal)
        val_loader = DataLoader(val_ds, shuffle=False, **kwargs)

    return train_loader, val_loader


def train_nn_model(config: Config, model_name: str) -> str:
    """Trains a gradient-based model (convlstm / fusion_convlstm). Returns
    the path to the final checkpoint."""
    set_seed(config.train.seed)
    device = torch.device(
        config.train.device if (config.train.device != "cuda" or torch.cuda.is_available()) else "cpu"
    )

    # NOTE: build_dataloaders must run before build_model when
    # data_source == "m2" — it replaces config.data with the contract
    # derived from the real M2 bundle (real channel count / grid size /
    # target type), which build_model needs in order to size the network
    # correctly. This ordering is a no-op for data_source == "synthetic".
    train_loader, val_loader = build_dataloaders(config, model_name)
    model = build_model(model_name, config.data, config.train).to(device)

    loss_fn = get_loss(config.train.loss, config.data)
    optimizer = (
        torch.optim.Adam(model.parameters(), lr=config.train.learning_rate, weight_decay=config.train.weight_decay)
        if config.train.optimizer == "adam"
        else torch.optim.SGD(model.parameters(), lr=config.train.learning_rate, weight_decay=config.train.weight_decay)
    )

    last_ckpt_path = None
    for epoch in range(1, config.train.epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = _to_device(xb, device), yb.to(device)
            optimizer.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * _batch_len(xb)
        train_loss /= len(train_loader.dataset)

        if val_loader is not None and len(val_loader.dataset) > 0:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb, yb = _to_device(xb, device), yb.to(device)
                    pred = model(xb)
                    val_loss += loss_fn(pred, yb).item() * _batch_len(xb)
            val_loss /= len(val_loader.dataset)
            val_str = f"val_loss={val_loss:.4f}"
        else:
            val_str = "val_loss=n/a (no val windows)"

        print(f"[{model_name}] epoch {epoch}/{config.train.epochs}  train_loss={train_loss:.4f}  {val_str}")

        if epoch % config.train.checkpoint_every_n_epochs == 0 or epoch == config.train.epochs:
            ckpt_path = os.path.join(config.train.checkpoint_dir, f"{model_name}_epoch{epoch}.pt")
            save_checkpoint(model, optimizer, epoch, config, ckpt_path)
            last_ckpt_path = ckpt_path
            print(f"  saved checkpoint: {ckpt_path}")

    return last_ckpt_path


def train_classical(config: Config) -> str:
    """Fits ClassicalMLBaseline over the full synthetic dataset in one shot
    (no epoch loop — sklearn estimators aren't trained via mini-batch SGD
    here) and saves it via its own joblib-based save()."""
    from src.models.classical_ml import ClassicalMLBaseline

    if config.train.data_source == "m2":
        from ml.training.strikecast_training.m2_bridge import build_m2_dataset, load_m2_bundle

        bundle = load_m2_bundle(config.train.m2_preprocessing_config, demo=config.train.m2_demo)
        config.data = DataContract.from_m2_bundle(bundle, multimodal=False)
        train_split = bundle.splits["train"]
        if len(train_split) == 0:
            raise ValueError(
                "M2's train split has 0 windows for the current preprocessing "
                "config — nothing to fit classical_ml on."
            )
        dataset = build_m2_dataset(train_split, config.data, multimodal=False)
    else:
        dataset = SyntheticDataset(config.data, num_samples=32, seed=config.train.seed)

    loader = DataLoader(dataset, batch_size=len(dataset), shuffle=False)
    xb, yb = next(iter(loader))

    model = ClassicalMLBaseline(config.data)
    model.fit(xb, yb)

    path = os.path.join(config.train.checkpoint_dir, "classical_ml.joblib")
    model.save(path)
    print(f"[classical_ml] fitted on {len(dataset)} samples, saved: {path}")
    return path


def _to_device(x, device):
    if isinstance(x, dict):
        return {k: v.to(device) for k, v in x.items()}
    return x.to(device)


def _batch_len(x) -> int:
    if isinstance(x, dict):
        return next(iter(x.values())).shape[0]
    return x.shape[0]


def main():
    parser = argparse.ArgumentParser(description="StrikeCast M3 training entrypoint")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config")
    parser.add_argument("--model", type=str, default="convlstm",
                         choices=["convlstm", "fusion_convlstm", "classical_ml"],
                         help="Which model to train (persistence needs no training)")
    parser.add_argument("--data-source", type=str, default=None, choices=["synthetic", "m2"],
                         help="Override config's train.data_source (default: whatever the config says, "
                              "or 'synthetic' with no config)")
    parser.add_argument("--m2-config", type=str, default=None,
                         help="Path to M2's preprocessing_config.yaml (default: M2's own default path)")
    args = parser.parse_args()

    # The scientific real-data config follows the observation-aware raw-data
    # contract, not the legacy synthetic/M2 contract. Route it to the canonical
    # ERA5/LIS builder; it blocks before fit when coverage or labels are absent.
    if args.config and Path(args.config).name == "real_data.yaml":
        root=Path(__file__).resolve().parents[3]
        command=[sys.executable,str(root/"scripts/ml/run_real_training.py"),"--config",str(Path(args.config).resolve())]
        raise SystemExit(subprocess.run(command,cwd=root).returncode)

    config = load_config(args.config)
    if args.data_source is not None:
        config.train.data_source = args.data_source
    if args.m2_config is not None:
        config.train.m2_preprocessing_config = args.m2_config

    if args.model == "classical_ml":
        train_classical(config)
    else:
        train_nn_model(config, args.model)


if __name__ == "__main__":
    main()
