from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest

from resolveit_core.calibrate.conformal_selective import (
    conformal_quantile,
    fit_conformal,
    fit_temperature,
    log_binom_cdf,
    select_tau,
    softmax,
)

K = 12


def synth(rng: np.random.Generator, n_per_class: int, signal: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    y = np.repeat(np.arange(K), n_per_class)
    logits = rng.normal(size=(len(y), K))
    logits[np.arange(len(y)), y] += signal
    return logits, y


def test_temperature_recovers_known_scale() -> None:
    rng = np.random.default_rng(1)
    n = 20_000
    true_logits = rng.normal(size=(n, K)) * 2.0
    y = np.array([rng.choice(K, p=p) for p in softmax(true_logits)])
    t = fit_temperature(true_logits * 3.0, y)
    assert abs(t - 3.0) < 0.15


def test_quantile_index_and_infinite_threshold() -> None:
    scores = np.arange(1, 10, dtype=np.float64)  # n = 9, alpha = 0.1 -> ceil(10 * 0.9) = 9th
    assert conformal_quantile(scores, 0.10) == 9.0
    assert conformal_quantile(scores[:8], 0.10) == math.inf  # n = 8 -> index 9 > n
    assert conformal_quantile(np.arange(1, 20, dtype=np.float64), 0.10) == 18.0


def test_small_classes_fall_back_to_pooled_and_are_flagged() -> None:
    rng = np.random.default_rng(2)
    logits, y = synth(rng, 150)
    keep = ~((y == 11) & (np.arange(len(y)) % 3 != 0))  # class 11 keeps 50 points
    cal = fit_conformal(softmax(logits[keep]), y[keep], alpha=0.10)
    assert cal.class_conditional[:11].all() and not cal.class_conditional[11]
    assert cal.thresholds[11] == cal.pooled_threshold
    assert cal.class_counts[11] == 50


def test_empty_set_is_possible_and_reported() -> None:
    rng = np.random.default_rng(3)
    logits, y = synth(rng, 150, signal=6.0)
    cal = fit_conformal(softmax(logits), y)
    assert cal.predict_set(np.full(K, 1.0 / K)) == []


@pytest.mark.slow
def test_class_conditional_coverage_simulation_1000_trials() -> None:
    rng = np.random.default_rng(4)
    alpha, n_cal, n_test, trials = 0.10, 150, 100, 1000
    covered = np.zeros(K)
    for t in range(trials):
        cl, cy = synth(rng, n_cal)
        tl, ty = synth(rng, n_test)
        cal = fit_conformal(softmax(cl), cy, alpha=alpha, seed=t)
        sets = cal.predict_sets(softmax(tl))
        hit = sets[np.arange(len(ty)), ty]
        covered += np.bincount(ty, weights=hit.astype(np.float64), minlength=K) / n_test
    coverage = covered / trials
    lower, upper = 1 - alpha, 1 - alpha + 1 / (n_cal + 1)
    slack = 0.005  # Monte Carlo error at 1000 trials
    assert (coverage >= lower - slack).all(), coverage
    assert (coverage <= upper + slack).all(), coverage


def test_log_binom_cdf_matches_direct_sum() -> None:
    for n, k, p in [(60, 0, 0.05), (300, 8, 0.05), (300, 9, 0.05), (25, 25, 0.3), (5000, 200, 0.05)]:
        q = Fraction(p).limit_denominator(1000)
        direct = float(sum(math.comb(n, j) * q**j * (1 - q) ** (n - j) for j in range(k + 1)))
        assert math.isclose(math.exp(log_binom_cdf(k, n, p)), direct, rel_tol=1e-9)
    assert math.exp(log_binom_cdf(8, 300, 0.05)) <= 0.05 < math.exp(log_binom_cdf(9, 300, 0.05))
    assert math.exp(log_binom_cdf(0, 60, 0.05)) <= 0.05 < math.exp(log_binom_cdf(0, 58, 0.05))


def test_select_tau_none_when_nothing_certifiable() -> None:
    rng = np.random.default_rng(5)
    conf = rng.uniform(0.5, 1.0, size=2000)
    res = select_tau(conf, rng.random(2000) < 0.30)
    assert res.tau_hat is None and res.steps and not res.steps[-1].passed


def test_select_tau_certifies_clean_model_and_starts_at_min_routed() -> None:
    rng = np.random.default_rng(6)
    conf = rng.uniform(0.5, 1.0, size=3000)
    res = select_tau(conf, np.zeros(3000, dtype=bool))
    assert res.tau_hat == 0.50
    assert res.steps[0].n_routed >= 60
    assert all(a.tau > b.tau for a, b in zip(res.steps, res.steps[1:], strict=False))


@pytest.mark.slow
@pytest.mark.parametrize("n", [1800, 6000])
def test_selective_risk_violation_rate_1000_trials(n: int) -> None:
    """conf ~ U(0.4, 1); P(error | conf) = 1.3 (1 - conf)  =>  risk(tau) = 0.65 (1 - tau)."""
    rng = np.random.default_rng(7 + n)
    epsilon, delta, trials = 0.05, 0.05, 1000
    violations = certified = 0
    for _ in range(trials):
        conf = rng.uniform(0.4, 1.0, size=n)
        err = rng.random(n) < 1.3 * (1.0 - conf)
        res = select_tau(conf, err, epsilon=epsilon, delta=delta)
        if res.tau_hat is not None:
            certified += 1
            violations += 0.65 * (1.0 - res.tau_hat) > epsilon
    assert violations / trials <= delta + 0.02, violations / trials
    print(f"n={n}: certified {certified / trials:.1%}, violations {violations / trials:.1%}")
