"""
Inference entrypoint. Independent of training code — only depends on a
saved checkpoint (self-describing: contains the config needed to rebuild
the model) plus input data.

    python -m src.inference.predict --checkpoint checkpoints/convlstm_epoch5.pt
    python -m src.inference.predict --checkpoint checkpoints/classical_ml.joblib --model classical_ml

By default, inference reproduces the checkpoint's own `config.train.data_source`:
a model trained with `data_source: synthetic` runs on one synthetic sample
(shape/plumbing demo, as before); a model trained with `data_source: m2`
runs on one real window pulled from M2's build_dataset() (see
src/training/m2_bridge.py) — the same real data the model was trained on,
not a shape-matched stand-in. Override with --data-source / --split.
"""

import argparse
import torch

from ml.training.strikecast_training.checkpoint import load_checkpoint
from ml.training.strikecast_training.dataset import SyntheticDataset
from ml.training.strikecast_training.seed import set_seed
from src.models.schema import ModelOutput


def _get_real_m2_sample(config, split: str, device: str):
    """Pull one real (x, y) pair from M2's build_dataset(), using the same
    m2_preprocessing_config/m2_demo the checkpoint was trained with. Falls
    back to 'train' with a warning if the requested split has 0 windows —
    a documented possibility on small/demo data (docs/m2_m3_contract.md)."""
    from ml.training.strikecast_training.m2_bridge import build_m2_dataset, load_m2_bundle

    multimodal = len(config.data.modalities) > 1
    bundle = load_m2_bundle(config.train.m2_preprocessing_config, demo=config.train.m2_demo)

    window_split = bundle.splits.get(split)
    if window_split is None or len(window_split) == 0:
        print(f"[m2 data] warning: '{split}' split has 0 windows — falling back to 'train'.")
        split = "train"
        window_split = bundle.splits["train"]
    if len(window_split) == 0:
        raise ValueError("M2's train split also has 0 windows — no real sample available.")

    ds = build_m2_dataset(window_split, config.data, multimodal)
    x, y = ds[0]
    print(f"[m2 data] using window 0 of '{split}' split ({len(window_split)} windows available).")
    if isinstance(x, dict):
        return {k: v.unsqueeze(0).to(device) for k, v in x.items()}, y.unsqueeze(0).to(device)
    return x.unsqueeze(0).to(device), y.unsqueeze(0).to(device)


def run_inference_nn(checkpoint_path: str, device: str = "cpu",
                      data_source: str = None, split: str = "test") -> ModelOutput:
    model, _, epoch, config = load_checkpoint(checkpoint_path, device=device)
    set_seed(config.train.seed)  # deterministic synthetic sample for demo purposes

    source = data_source or config.train.data_source
    if source == "m2":
        x, _y = _get_real_m2_sample(config, split, device)
    else:
        demo_dataset = SyntheticDataset(config.data, num_samples=1, seed=config.train.seed + 1)
        x, _ = demo_dataset[0]
        if isinstance(x, dict):
            x = {k: v.unsqueeze(0).to(device) for k, v in x.items()}  # add batch dim
        else:
            x = x.unsqueeze(0).to(device)

    output = model.predict(x)
    print(f"Loaded checkpoint from epoch {epoch}, model={model.model_name} v{model.model_version}")
    print(f"Prediction shape: {tuple(output.prediction.shape)}")
    return output


def run_inference_classical(checkpoint_path: str, data_source: str = "synthetic", split: str = "test") -> ModelOutput:
    from src.models.classical_ml import ClassicalMLBaseline

    model = ClassicalMLBaseline.load(checkpoint_path)

    if data_source == "m2":
        from ml.training.strikecast_training.m2_bridge import build_m2_dataset, load_m2_bundle

        bundle = load_m2_bundle(demo=True)
        window_split = bundle.splits.get(split) or bundle.splits["train"]
        if len(window_split) == 0:
            window_split = bundle.splits["train"]
        ds = build_m2_dataset(window_split, model.contract, multimodal=False)
        x, _ = ds[0]
    else:
        demo_dataset = SyntheticDataset(model.contract, num_samples=1, seed=1)
        x, _ = demo_dataset[0]
    x = x.unsqueeze(0)

    output = model.predict(x)
    print(f"Loaded classical_ml checkpoint, model={model.model_name} v{model.model_version}")
    print(f"Prediction shape: {tuple(output.prediction.shape)}")
    return output


def run_inference_persistence(data_contract=None) -> ModelOutput:
    """Persistence has no checkpoint — it's parameter-free — so inference
    just needs the DataContract to know expected shapes."""
    from src.models.persistence import PersistenceBaseline
    from ml.training.strikecast_training.config import DataContract

    contract = data_contract or DataContract(
        input_channel_names=["lightning_strike_count"],
        lightning_channel_index=0,
        lightning_zero_threshold=0.0,
    )
    model = PersistenceBaseline(contract)
    demo_dataset = SyntheticDataset(contract, num_samples=1, seed=1)
    x, _ = demo_dataset[0]
    x = x.unsqueeze(0)

    output = model.predict(x)
    print(f"Persistence baseline (no checkpoint needed)")
    print(f"Prediction shape: {tuple(output.prediction.shape)}")
    return output


def main():
    parser = argparse.ArgumentParser(description="StrikeCast M3 inference entrypoint")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to checkpoint (.pt or .joblib)")
    parser.add_argument("--model", type=str, default="convlstm",
                         choices=["convlstm", "fusion_convlstm", "classical_ml", "persistence"])
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--data-source", type=str, default=None, choices=["synthetic", "m2"],
                         help="Override the checkpoint's own data_source for this inference call")
    parser.add_argument("--split", type=str, default="test", choices=["train", "val", "test"],
                         help="Which M2 split to pull the demo sample from when data_source=m2")
    args = parser.parse_args()

    if args.model == "persistence":
        run_inference_persistence()
    elif args.model == "classical_ml":
        if args.checkpoint is None:
            raise ValueError("--checkpoint is required for classical_ml")
        run_inference_classical(args.checkpoint, data_source=args.data_source or "synthetic", split=args.split)
    else:
        if args.checkpoint is None:
            raise ValueError("--checkpoint is required for convlstm/fusion_convlstm")
        run_inference_nn(args.checkpoint, device=args.device, data_source=args.data_source, split=args.split)


if __name__ == "__main__":
    main()
