"""Histogram-gradient-boosting baseline over flattened causal windows.

This research-only estimator shares the logistic baseline's feature/target
contract. It must be fit on TRAIN windows and evaluated on a common held-out
split; joblib artifacts remain untrusted research files, not serving models.
"""
from sklearn.ensemble import HistGradientBoostingClassifier

from src.models.classical_ml import ClassicalMLBaseline


class TreeMLBaseline(ClassicalMLBaseline):
    model_name = "tree_ml"
    model_version = "1.0.0"

    def __init__(self, contract, seed: int = 0):
        super().__init__(contract, seed=seed)
        if contract.target_type != "binary":
            raise ValueError("TreeMLBaseline currently supports binary targets only")
        self._estimator = HistGradientBoostingClassifier(
            max_iter=100, max_leaf_nodes=15, random_state=seed
        )
