"""
Model factory. Centralizes "given a model_name string, build the right
model object" so train.py, checkpoint.py, and inference/predict.py never
duplicate this logic or drift out of sync.
"""

from ml.training.strikecast_training.config import DataContract, TrainConfig
from src.models.persistence import PersistenceBaseline
from src.models.climatology import ClimatologyBaseline
from src.models.classical_ml import ClassicalMLBaseline
from src.models.tree_ml import TreeMLBaseline
from src.models.convlstm import ConvLSTM
from src.models.fusion import FusionConvLSTM


def build_model(model_name: str, contract: DataContract, train_cfg: TrainConfig = None):
    if model_name == "persistence":
        return PersistenceBaseline(contract)
    elif model_name == "climatology":
        return ClimatologyBaseline(contract)
    elif model_name == "classical_ml":
        return ClassicalMLBaseline(contract)
    elif model_name == "tree_ml":
        return TreeMLBaseline(contract)
    elif model_name == "convlstm":
        hidden_dims = train_cfg.conv_hidden_dims if train_cfg else None
        kernel_size = train_cfg.conv_kernel_size if train_cfg else 3
        return ConvLSTM(contract, hidden_dims=hidden_dims, kernel_size=kernel_size)
    elif model_name == "fusion_convlstm":
        hidden_dims = train_cfg.conv_hidden_dims if train_cfg else None
        kernel_size = train_cfg.conv_kernel_size if train_cfg else 3
        return FusionConvLSTM(contract, encoder_hidden_dims=hidden_dims, kernel_size=kernel_size)
    else:
        raise ValueError(
            f"Unknown model_name '{model_name}'. "
            f"Expected one of: climatology, persistence, classical_ml, tree_ml, convlstm, fusion_convlstm"
        )
