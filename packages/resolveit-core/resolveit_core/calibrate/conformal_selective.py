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
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be positive")
    raw = np.asarray(logits, dtype=np.float64)
    if raw.ndim < 1 or raw.shape[-1] == 0 or not np.isfinite(raw).all():
        raise ValueError("logits must be finite with nonempty class dimension")
    z = raw / temperature
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
    if logits.ndim != 2 or labels.ndim != 1 or not np.isfinite(logits).all():
        raise ValueError("finite (n, classes) logits and 1-D labels required")
    if np.any((labels < 0) | (labels >= logits.shape[1])):
        raise ValueError("class label outside model output")
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
    if not 0 < alpha < 1 or scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("finite 1-D scores and alpha in (0, 1) required")
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

    Calibration scores get tiny positive seeded jitter. Prediction uses `<=`
    without jitter, which is conservative for lower coverage. An upper coverage
    bound is NOT claimed for discrete/tied model outputs.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    if p.ndim != 2 or len(p) != len(y) or len(y) == 0:
        raise ValueError("probs must be (n, classes) and match labels")
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)) or not np.allclose(p.sum(1), 1):
        raise ValueError("probs must be finite probability rows")
    if np.any((y < 0) | (y >= p.shape[1])) or min_class_n < 1:
        raise ValueError("invalid class labels or support floor")
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
    risk_upper: float = 1.0


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
    """Simultaneous exact-binomial tests across a predeclared threshold grid.

    Bonferroni controls adaptive choice of the lowest passing threshold. A
    sparse or failing high-confidence tail cannot lock out a well-supported
    lower threshold. This may need more labels than a fixed-sequence test;
    no approximate interval is used to manufacture a certificate.

    Inputs must come from an independent random-audit certification split.
    Temperature, conformal thresholds, costs and all other eligibility rules
    must already be frozen. Filter to the actual gate-eligible population
    before calling; posterior-after-answer traffic needs separate validation.
    """
    conf = np.asarray(confidence, dtype=np.float64)
    err = np.asarray(misrouted, dtype=np.bool_)
    if conf.shape != err.shape or conf.ndim != 1:
        raise ValueError("confidence and misrouted must be 1-D and aligned")
    if not np.isfinite(conf).all() or np.any((conf < 0) | (conf > 1)):
        raise ValueError("confidence must be finite probabilities")
    if not (0 < epsilon < 1 and 0 < delta < 1):
        raise ValueError("epsilon and delta must be in (0, 1)")
    if not (0 <= tau_min <= tau_max <= 1 and math.isfinite(step) and step > 0):
        raise ValueError("invalid threshold grid")
    if min_routed < 1:
        raise ValueError("min_routed must be positive")
    intervals = (tau_max - tau_min) / step
    if not math.isfinite(intervals) or intervals > 10_000:
        raise ValueError("threshold grid must contain at most 10002 points")
    n_grid = math.floor(intervals + 1e-12) + 1
    grid = [max(tau_min, tau_max - i * step) for i in range(n_grid)]
    if not math.isclose(grid[-1], tau_min, abs_tol=1e-12):
        grid.append(tau_min)
    else:
        grid[-1] = tau_min
    steps: list[TauStep] = []
    tau_hat: float | None = None
    test_delta = delta / len(grid)
    for tau in grid:
        routed = conf >= tau
        n = int(routed.sum())
        if n < min_routed:
            continue
        k = int(err[routed].sum())
        p_value = math.exp(log_binom_cdf(k, n, epsilon))
        passed = p_value <= test_delta
        # A coarse valid upper confidence limit avoids repeated numerical
        # inversion in threshold sweeps. Full inversion remains available to
        # reports via binomial_risk_upper().
        upper = epsilon if passed else 1.0
        steps.append(TauStep(tau, n, k, p_value, passed, upper))
        if passed:
            tau_hat = tau
    return SelectiveRiskResult(tau_hat, epsilon, delta, tuple(steps))


def binomial_risk_upper(errors: int, n: int, delta: float) -> float:
    """One-sided exact Clopper-Pearson upper limit; no scipy runtime dependency."""
    if n < 0 or not 0 <= errors <= n or not 0 < delta < 1:
        raise ValueError("invalid binomial bound inputs")
    if n == 0 or errors == n:
        return 1.0
    if errors == 0:
        return -math.expm1(math.log(delta) / n)
    lo, hi = errors / n, 1.0
    target = math.log(delta)
    for _ in range(48):
        mid = (lo + hi) / 2
        if log_binom_cdf(errors, n, mid) > target:
            lo = mid
        else:
            hi = mid
    return hi


def empirical_bernstein_upper(errors: int, n: int, delta: float) -> float:
    """Finite-sample variance-adaptive bound for independent Bernoulli losses.

    Diagnostic alternative to exact binomial bounds. Taking the minimum of
    two bounds requires splitting their error budget; Wilson is not an exact
    finite-sample certificate and is intentionally excluded.
    """
    if n < 0 or not 0 <= errors <= n or not 0 < delta < 1:
        raise ValueError("invalid empirical Bernstein inputs")
    if n < 2:
        return 1.0
    mean = errors / n
    variance = n * mean * (1 - mean) / (n - 1)
    log_term = math.log(2 / delta)
    return min(1.0, mean + math.sqrt(2 * variance * log_term / n) + 7 * log_term / (3 * (n - 1)))


def select_queue_taus(
    confidence: FloatArray,
    misrouted: BoolArray,
    predicted_queue: IntArray,
    *,
    n_queues: int,
    epsilon: float = 0.05,
    delta: float = 0.05,
    min_routed: int = 150,
) -> dict[int, SelectiveRiskResult]:
    """Graduate queues independently, with one family-wise error budget.

    Low-support queues return tau_hat=None. No global certificate may be
    borrowed by a queue without evidence. Queue labels are the frozen
    cost-minimising predictions, not true labels or argmax when costs differ.
    """
    queue = np.asarray(predicted_queue, dtype=np.int64)
    conf = np.asarray(confidence, dtype=np.float64)
    err = np.asarray(misrouted, dtype=np.bool_)
    if n_queues < 1 or queue.ndim != 1 or queue.shape != conf.shape or queue.shape != err.shape:
        raise ValueError("queue, confidence and errors must align")
    if np.any((queue < 0) | (queue >= n_queues)):
        raise ValueError("predicted queue outside declared queue family")
    return {
        q: select_tau(conf[queue == q], err[queue == q], epsilon, delta / n_queues, min_routed=min_routed)
        for q in range(n_queues)
    }


__all__ = [
    "ConformalCalibrator",
    "SelectiveRiskResult",
    "TauStep",
    "binomial_risk_upper",
    "conformal_quantile",
    "empirical_bernstein_upper",
    "fit_conformal",
    "fit_temperature",
    "log_binom_cdf",
    "nll",
    "select_queue_taus",
    "select_tau",
    "softmax",
]
