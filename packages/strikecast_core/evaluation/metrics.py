from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Sequence


@dataclass(frozen=True)
class EvaluationMetrics:
    n: int
    positive_count: int
    event_frequency: float
    threshold: float
    brier_score: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    pod: float
    far: float
    csi: float
    roc_auc: float | None
    pr_auc: float | None
    ece: float
    confusion_matrix: tuple[tuple[int, int], tuple[int, int]]

    def to_dict(self) -> dict:
        return asdict(self)


def _round_metric(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _roc_auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    order = sorted(range(len(scores)), key=scores.__getitem__)
    rank_sum = 0.0
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        average_rank = ((i + 1) + j) / 2.0
        rank_sum += average_rank * sum(labels[order[k]] for k in range(i, j))
        i = j
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _average_precision(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    if not positives or positives == len(labels):
        return None
    order = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
    true_positives = false_positives = 0
    previous_recall = 0.0
    area = 0.0
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            if labels[order[j]]:
                true_positives += 1
            else:
                false_positives += 1
            j += 1
        recall = true_positives / positives
        precision = true_positives / (true_positives + false_positives)
        area += (recall - previous_recall) * precision
        previous_recall = recall
        i = j
    return area


def evaluate_binary_classifier(
    y_true: Sequence[int],
    probabilities: Sequence[float],
    threshold: float = 0.5,
    ece_bins: int = 10,
) -> EvaluationMetrics:
    if len(y_true) != len(probabilities) or len(y_true) == 0:
        raise ValueError("y_true and probabilities must have same non-zero length")
    if ece_bins < 1:
        raise ValueError("ece_bins must be positive")
    raw_labels = list(y_true)
    if any(y not in (0, 1) for y in raw_labels):
        raise ValueError("y_true must contain binary 0/1 labels")
    labels = [int(y) for y in raw_labels]
    scores = [float(p) for p in probabilities]
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in scores):
        raise ValueError("probabilities must be finite and within [0, 1]")
    if not math.isfinite(float(threshold)) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and within [0, 1]")

    predicted = [int(p >= threshold) for p in scores]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predicted))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predicted))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predicted))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predicted))
    n = len(labels)
    precision = tp / (tp + fp) if tp + fp else 0.0
    pod = tp / (tp + fn) if tp + fn else 0.0
    far = fp / (tp + fp) if tp + fp else 0.0
    csi = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    f1 = 2 * precision * pod / (precision + pod) if precision + pod else 0.0
    brier = sum((p - y) ** 2 for y, p in zip(labels, scores)) / n
    ece = 0.0
    for bin_index in range(ece_bins):
        lower, upper = bin_index / ece_bins, (bin_index + 1) / ece_bins
        members = [i for i, p in enumerate(scores) if lower <= p < upper or (bin_index == ece_bins - 1 and p == 1)]
        if members:
            observed = sum(labels[i] for i in members) / len(members)
            forecast = sum(scores[i] for i in members) / len(members)
            ece += len(members) / n * abs(observed - forecast)

    return EvaluationMetrics(
        n=n,
        positive_count=sum(labels),
        event_frequency=_round_metric(sum(labels) / n),
        threshold=float(threshold),
        brier_score=_round_metric(brier),
        accuracy=_round_metric((tp + tn) / n),
        precision=_round_metric(precision),
        recall=_round_metric(pod),
        f1=_round_metric(f1),
        pod=_round_metric(pod),
        far=_round_metric(far),
        csi=_round_metric(csi),
        roc_auc=_round_metric(_roc_auc(labels, scores)),
        pr_auc=_round_metric(_average_precision(labels, scores)),
        ece=_round_metric(ece),
        confusion_matrix=((tn, fp), (fn, tp)),
    )
