"""Four benchmark baselines without fabricating external LLM predictions.

TF-IDF/logistic fit consumes training data only. Frozen test logits feed forced
single-label and naive confidence policies. Zero-shot requires independently
recorded external predictions and reports annotation-family bias explicitly.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from resolveit_core.calibrate.conformal_selective import softmax

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class Metrics:
    coverage: float
    selective_error: float | None
    accuracy: float
    n: int


def metrics(predictions: IntArray, truth: IntArray) -> Metrics:
    pred, y = np.asarray(predictions), np.asarray(truth)
    if pred.ndim != 1 or pred.shape != y.shape or len(y) == 0:
        raise ValueError("nonempty aligned predictions and labels required")
    selected = pred >= 0
    return Metrics(float(selected.mean()), float(np.mean(pred[selected] != y[selected]))
                   if selected.any() else None, float(np.mean(pred == y)), len(y))


def forced_single_label(probs: FloatArray) -> IntArray:
    return np.asarray(np.argmax(probs, axis=1), dtype=np.int64)


def naive_confidence(probs: FloatArray, threshold: float = 0.8) -> IntArray:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be a probability")
    pred = forced_single_label(probs)
    pred[np.max(probs, axis=1) < threshold] = -1
    return pred


def zero_shot_cached(
    predictions: IntArray | None, truth: IntArray, *, model_family: str, silver_annotator_family: str | None,
) -> tuple[Metrics | None, bool]:
    """Missing external inference stays missing. Never simulate zero-shot results."""
    bias = silver_annotator_family is not None and model_family == silver_annotator_family
    return (None if predictions is None else metrics(predictions, truth)), bias


class TfidfLogistic:
    """Bounded Unicode word TF-IDF plus multiclass logistic regression."""

    def __init__(self, n_classes: int, max_features: int = 2000) -> None:
        self.n_classes = n_classes
        self.max_features = max_features
        self.vocabulary: dict[str, int] = {}
        self.idf = np.empty(0)
        self.weights = np.empty((0, n_classes))

    @staticmethod
    def tokens(text: str) -> list[str]:
        # Whitespace tokens preserve Devanagari combining marks; ASCII \w
        # tokenization would fragment Hindi vowel signs.
        return [t for t in re.split(r"\s+", text.casefold()) if t]

    def transform(self, texts: Sequence[str]) -> FloatArray:
        x = np.zeros((len(texts), len(self.vocabulary) + 1), dtype=np.float64)
        for i, text in enumerate(texts):
            for token, count in Counter(self.tokens(text)).items():
                if token in self.vocabulary:
                    j = self.vocabulary[token]
                    x[i, j] = (1 + np.log(count)) * self.idf[j]
        norms = np.linalg.norm(x[:, :-1], axis=1, keepdims=True)
        x[:, :-1] /= np.maximum(norms, 1e-12)
        x[:, -1] = 1
        return x

    def fit(self, texts: Sequence[str], labels: IntArray, epochs: int = 150) -> None:
        if len(texts) != len(labels) or not texts or np.any((labels < 0) | (labels >= self.n_classes)):
            raise ValueError("valid training texts and labels required")
        docs: Counter[str] = Counter(t for text in texts for t in set(self.tokens(text)))
        ordered = sorted(docs, key=lambda t: (-docs[t], t))[:self.max_features]
        self.vocabulary = {t: i for i, t in enumerate(ordered)}
        self.idf = np.array([np.log((1 + len(texts)) / (1 + docs[t])) + 1 for t in ordered])
        x = self.transform(texts)
        self.weights = np.zeros((x.shape[1], self.n_classes))
        for _ in range(epochs):
            gradient = softmax(x @ self.weights)
            gradient[np.arange(len(labels)), labels] -= 1
            self.weights -= 0.5 * (x.T @ gradient / len(labels) + 1e-4 * self.weights)

    def predict(self, texts: Sequence[str]) -> IntArray:
        if self.weights.size == 0:
            raise ValueError("baseline must be fitted first")
        return np.asarray(np.argmax(self.transform(texts) @ self.weights, axis=1), dtype=np.int64)


def paired_bootstrap_accuracy(
    first: IntArray, second: IntArray, truth: IntArray, *, resamples: int = 2000, seed: int = 0,
) -> tuple[float, float, float]:
    """Paired percentile bootstrap CI for accuracy difference; no coverage claim."""
    if first.shape != second.shape or first.shape != truth.shape or truth.ndim != 1 or not len(truth):
        raise ValueError("paired predictions and labels must align")
    if resamples < 100:
        raise ValueError("at least 100 resamples required")
    differences = (first == truth).astype(float) - (second == truth).astype(float)
    rng = np.random.default_rng(seed)
    draws = np.array([differences[rng.integers(0, len(truth), len(truth))].mean() for _ in range(resamples)])
    return float(differences.mean()), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))
