"""Temperature scaling, class-conditional conformal sets, selective-risk threshold.

Every function here must be fed outputs of the SHIPPED INT8 ONNX model.
Fitting on FP32 logits and serving INT8 is a release-blocking bug.

Guarantees (under exchangeability of calibration and live data):
  * class-conditional coverage  P(Y in C(X) | Y = y) >= 1 - alpha  for teams
    with their own threshold;
  * selective risk  P(misroute | routed) <= epsilon  with probability at
    least 1 - delta over the calibration draw.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]


def softmax(logits: FloatArray, temperature: float = 1.0) -> FloatArray:
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    z = np.asarray(logits, dtype=np.float64) / temperature
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    out: FloatArray = e / e.sum(axis=-1, keepdims=True)
    return out


def nll(logits: FloatArray, labels: IntArray, temperature: float) -> float:
    z = np.asarray(logits, dtype=np.float64) / temperature
    z = z - z.max(axis=1, keepdims=True)
    log_z = np.log(np.exp(z).sum(axis=1))
    return float(np.mean(log_z - z[np.arange(len(labels)), labels]))


def fit_temperature(logits: FloatArray, labels: IntArray) -> float:
    """Minimise NLL over T by golden-section search on log T in [-3, 3]."""
    if len(logits) != len(labels) or len(labels) == 0:
        raise ValueError("need matching, non-empty logits and labels")
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    lo, hi = -3.0, 3.0
    c, d = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fc, fd = nll(logits, labels, math.exp(c)), nll(logits, labels, math.exp(d))
    for _ in range(80):
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - phi * (hi - lo)
            fc = nll(logits, labels, math.exp(c))
        else:
            lo, c, fc = c, d, fd
            d = lo + phi * (hi - lo)
            fd = nll(logits, labels, math.exp(d))
    return math.exp((lo + hi) / 2.0)


def conformal_quantile(scores: FloatArray, alpha: float) -> float:
    """The ceil((n+1)(1-alpha))-th smallest score; +inf when that index exceeds n."""
    n = len(scores)
    k = math.ceil((n + 1) * (1.0 - alpha) - 1e-12)
    if n == 0 or k > n:
        return math.inf
    return float(np.partition(scores, k - 1)[k - 1])


@dataclass(frozen=True, slots=True)
class ConformalCalibrator:
    alpha: float
    thresholds: FloatArray  # per class
    class_conditional: BoolArray  # True where the class has its own threshold
    pooled_threshold: float
    class_counts: IntArray

    def predict_set(self, probs: FloatArray) -> list[int]:
        """Classes y with 1 - p_y <= q_y. May be empty: caller must DEFER."""
        p = np.asarray(probs, dtype=np.float64)
        return [int(i) for i in np.flatnonzero((1.0 - p) <= self.thresholds)]

    def predict_sets(self, probs: FloatArray) -> BoolArray:
        out: BoolArray = (1.0 - np.asarray(probs, dtype=np.float64)) <= self.thresholds[None, :]
        return out


def fit_conformal(
    probs: FloatArray,
    labels: IntArray,
    alpha: float = 0.10,
    min_class_n: int = 150,
    seed: int = 0,
) -> ConformalCalibrator:
    """Class-conditional split conformal with pooled fallback for small classes.

    Scores get a tiny seeded jitter so ties are broken and the upper coverage
    bound applies. Prediction uses `<=` without jitter, which is conservative.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    if p.ndim != 2 or len(p) != len(y) or len(y) == 0:
        raise ValueError("probs must be (n, classes) and match labels")
    n_classes = p.shape[1]
    rng = np.random.default_rng(seed)
    scores = 1.0 - p[np.arange(len(y)), y] + rng.uniform(0.0, 1e-9, size=len(y))
    pooled = conformal_quantile(scores, alpha)
    thresholds = np.full(n_classes, pooled, dtype=np.float64)
    own = np.zeros(n_classes, dtype=np.bool_)
    counts = np.bincount(y, minlength=n_classes).astype(np.int64)
    for c in range(n_classes):
        if counts[c] >= min_class_n:
            thresholds[c] = conformal_quantile(scores[y == c], alpha)
            own[c] = True
    return ConformalCalibrator(alpha, thresholds, own, pooled, counts)


def log_binom_cdf(k: int, n: int, p: float) -> float:
    """log P(Binomial(n, p) <= k), exact, stable for large n."""
    if k < 0:
        return -math.inf
    if k >= n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return -math.inf
    lp, lq = math.log(p), math.log1p(-p)
    terms = [
        math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1) + j * lp + (n - j) * lq
        for j in range(k + 1)
    ]
    m = max(terms)
    return min(0.0, m + math.log(sum(math.exp(t - m) for t in terms)))


@dataclass(frozen=True, slots=True)
class TauStep:
    tau: float
    n_routed: int
    n_errors: int
    p_value: float
    passed: bool


@dataclass(frozen=True, slots=True)
class SelectiveRiskResult:
    tau_hat: float | None  # None: nothing certified, tenant stays in shadow mode
    epsilon: float
    delta: float
    steps: tuple[TauStep, ...]


def select_tau(
    confidence: FloatArray,
    misrouted: BoolArray,
    epsilon: float = 0.05,
    delta: float = 0.05,
    tau_max: float = 0.99,
    tau_min: float = 0.50,
    step: float = 0.01,
    min_routed: int = 60,
) -> SelectiveRiskResult:
    """Learn-then-Test fixed-sequence search for the lowest certified tau.

    `misrouted[i]` must use the same action rule the gate uses (cost-minimising
    team != true team). Walks tau downward starting at the highest grid value
    with at least `min_routed` points, tests H: risk > epsilon with the exact
    binomial tail, and stops at the first failure. No multiplicity correction
    is needed because the order is fixed in advance.
    """
    conf = np.asarray(confidence, dtype=np.float64)
    err = np.asarray(misrouted, dtype=np.bool_)
    if conf.shape != err.shape or conf.ndim != 1:
        raise ValueError("confidence and misrouted must be 1-D and aligned")
    n_grid = round((tau_max - tau_min) / step) + 1
    grid = [round(tau_max - i * step, 10) for i in range(n_grid)]
    steps: list[TauStep] = []
    tau_hat: float | None = None
    started = False
    for tau in grid:
        routed = conf >= tau
        n = int(routed.sum())
        if not started:
            if n < min_routed:
                continue
            started = True
        k = int(err[routed].sum())
        p_value = math.exp(log_binom_cdf(k, n, epsilon))
        passed = p_value <= delta
        steps.append(TauStep(tau, n, k, p_value, passed))
        if not passed:
            break
        tau_hat = tau
    return SelectiveRiskResult(tau_hat, epsilon, delta, tuple(steps))


__all__ = [
    "ConformalCalibrator",
    "SelectiveRiskResult",
    "TauStep",
    "conformal_quantile",
    "fit_conformal",
    "fit_temperature",
    "log_binom_cdf",
    "nll",
    "select_tau",
    "softmax",
]
