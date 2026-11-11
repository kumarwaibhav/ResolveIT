"""Cost-sensitive ROUTE / ASK / DEFER gate with exact one-question EVSI.

Costs are minutes of delay. At most one question is ever asked, so the
one-step value-of-information calculation is exact, not a myopic bound.

The naive-Bayes update is coherent by construction:
    sum_a P(a | x) * p^a  ==  p
which is unit-tested to 1e-9.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from resolveit_core.calibrate.conformal_selective import ConformalCalibrator
from resolveit_core.schemas import N_TEAMS, UNKNOWN_ANSWER, Action, DeferReason, Slot

FloatArray = NDArray[np.float64]

MAX_ROUTABLE_SET_SIZE = 3  # a conformal set of 4 or more forbids ROUTE


@dataclass(frozen=True, slots=True)
class CostMatrix:
    """delay[y, k] = minutes lost when a ticket of true team y is sent to team k."""

    delay: FloatArray
    c_def: float  # median human triage minutes

    def __post_init__(self) -> None:
        d = self.delay
        if d.ndim != 2 or d.shape[0] != d.shape[1]:
            raise ValueError("cost matrix must be square")
        if np.any(d < 0) or np.any(np.diag(d) != 0):
            raise ValueError("costs must be non-negative with a zero diagonal")
        if self.c_def <= 0:
            raise ValueError("c_def must be positive")

    @classmethod
    def uniform(cls, misroute_minutes: float, c_def: float, n: int = N_TEAMS) -> CostMatrix:
        d = np.full((n, n), misroute_minutes, dtype=np.float64)
        np.fill_diagonal(d, 0.0)
        return cls(d, c_def)

    def scaled(self, factor: float) -> CostMatrix:
        if factor <= 0:
            raise ValueError("scale must be positive")
        return CostMatrix(self.delay * factor, self.c_def)


@dataclass(frozen=True, slots=True)
class ChannelCosts:
    c_ask: float  # minutes one question costs on this channel
    c_ghost: float  # extra minutes lost when the question goes unanswered
    asks: int = 0
    answers: int = 0

    @property
    def rho(self) -> float:
        """Posterior mean response rate under a Beta(1, 1) prior."""
        if self.answers > self.asks or self.asks < 0 or self.answers < 0:
            raise ValueError("invalid ask/answer counts")
        return (self.answers + 1) / (self.asks + 2)


class ThetaTable:
    """Smoothed P(answer a | slot k, team y). One (values x teams) array per slot."""

    def __init__(
        self,
        values: Mapping[Slot, Sequence[str]],
        n_teams: int = N_TEAMS,
        kappa: float = 10.0,
    ) -> None:
        if kappa <= 0:
            raise ValueError("kappa must be positive")
        self.kappa = kappa
        self.n_teams = n_teams
        self.values: dict[Slot, tuple[str, ...]] = {}
        self.counts: dict[Slot, FloatArray] = {}
        for slot, vals in values.items():
            ordered = tuple(dict.fromkeys([*vals, UNKNOWN_ANSWER]))
            self.values[slot] = ordered
            self.counts[slot] = np.zeros((len(ordered), n_teams), dtype=np.float64)

    def add(self, slot: Slot, value: str, team: int, weight: float = 1.0) -> None:
        """Record one observation. Silver labels use weight 0.3, human labels 1.0."""
        if weight <= 0:
            raise ValueError("weight must be positive")
        self.counts[slot][self.values[slot].index(value), team] += weight

    def theta(self, slot: Slot) -> FloatArray:
        """theta[a, y] = (n[a, y] + kappa * pi[a]) / (n[., y] + kappa); columns sum to 1."""
        n = self.counts[slot]
        total = n.sum()
        pi = n.sum(axis=1) / total if total > 0 else np.full(n.shape[0], 1.0 / n.shape[0])
        out: FloatArray = (n + self.kappa * pi[:, None]) / (n.sum(axis=0, keepdims=True) + self.kappa)
        return out

    def n_cells(self) -> int:
        return sum(c.size for c in self.counts.values())


def bayes_update(probs: FloatArray, theta_slot: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Return P(a | x) (n_values,) and posteriors p^a (n_values, n_teams)."""
    joint = theta_slot * probs[None, :]
    p_answer: FloatArray = joint.sum(axis=1)
    safe = np.where(p_answer > 0, p_answer, 1.0)
    post: FloatArray = joint / safe[:, None]
    return p_answer, post


def route_risk(
    probs: FloatArray,
    costs: CostMatrix,
    tau_hat: float | None,
    conformal_set: Sequence[int],
    critical_contradiction: bool,
) -> tuple[float, int]:
    """Expected delay of the cost-minimising route, or +inf if routing is not allowed."""
    expected = probs @ costs.delay
    k = int(np.argmin(expected))
    allowed = (
        tau_hat is not None
        and float(probs.max()) >= tau_hat
        and k in conformal_set
        and len(conformal_set) <= MAX_ROUTABLE_SET_SIZE
        and not critical_contradiction
    )
    return (float(expected[k]) if allowed else math.inf, k)


@dataclass(frozen=True, slots=True)
class SlotRisk:
    slot: Slot
    r_after: float
    r_ask: float


@dataclass(frozen=True, slots=True)
class GateInput:
    probs: FloatArray
    conformal: ConformalCalibrator
    costs: CostMatrix
    theta: ThetaTable
    channel: ChannelCosts
    askable_slots: tuple[Slot, ...]
    contradicted_critical: frozenset[Slot]
    tau_hat: float | None
    no_ask_holdout: bool = False


@dataclass(frozen=True, slots=True)
class GateOutput:
    action: Action
    team: int | None
    ask_slot: Slot | None
    defer_reason: DeferReason | None
    r_route: float
    r_now: float
    conformal_set: tuple[int, ...]
    slot_risks: tuple[SlotRisk, ...]


def ask_risk(inp: GateInput, slot: Slot, r_now: float) -> SlotRisk:
    values = inp.theta.values[slot]
    p_answer, post = bayes_update(inp.probs, inp.theta.theta(slot))
    r_after = 0.0
    for a, value in enumerate(values):
        if p_answer[a] <= 0:
            continue
        remaining = (
            inp.contradicted_critical if value == UNKNOWN_ANSWER else inp.contradicted_critical - {slot}
        )
        r_route_a, _ = route_risk(
            post[a], inp.costs, inp.tau_hat, inp.conformal.predict_set(post[a]), bool(remaining)
        )
        r_after += float(p_answer[a]) * min(r_route_a, inp.costs.c_def)
    rho = inp.channel.rho
    r_ask = inp.channel.c_ask + rho * r_after + (1.0 - rho) * (r_now + inp.channel.c_ghost)
    return SlotRisk(slot, r_after, r_ask)


def _defer_reason(inp: GateInput, cset: Sequence[int]) -> DeferReason:
    if inp.tau_hat is None:
        return DeferReason.SHADOW_MODE
    if len(cset) > MAX_ROUTABLE_SET_SIZE:
        return DeferReason.SET_TOO_LARGE
    if inp.contradicted_critical:
        return DeferReason.CRITICAL_CONTRADICTION
    return DeferReason.RISK_ABOVE_DEFER_COST


def decide(inp: GateInput) -> GateOutput:
    """Minimum expected delay over ROUTE, ASK (best slot), DEFER."""
    probs = np.asarray(inp.probs, dtype=np.float64)
    if probs.ndim != 1 or abs(float(probs.sum()) - 1.0) > 1e-6 or np.any(probs < 0):
        raise ValueError("probs must be a probability vector")
    cset = tuple(inp.conformal.predict_set(probs))
    if not cset:
        return GateOutput(
            Action.DEFER, None, None, DeferReason.NO_CONFORMING_TEAM, math.inf, inp.costs.c_def, cset, ()
        )
    r_route, team = route_risk(probs, inp.costs, inp.tau_hat, cset, bool(inp.contradicted_critical))
    r_now = min(r_route, inp.costs.c_def)
    risks = tuple(ask_risk(inp, slot, r_now) for slot in inp.askable_slots if slot in inp.theta.values)
    if risks and not inp.no_ask_holdout:
        best = min(risks, key=lambda r: r.r_ask)
        if best.r_ask < r_now:
            return GateOutput(Action.ASK, None, best.slot, None, r_route, r_now, cset, risks)
    if r_route <= inp.costs.c_def:
        return GateOutput(Action.ROUTE, team, None, None, r_route, r_now, cset, risks)
    return GateOutput(Action.DEFER, None, None, _defer_reason(inp, cset), r_route, r_now, cset, risks)


def finalize_after_answer(inp: GateInput, slot: Slot, answer: str | None) -> GateOutput:
    """Close a clarification and decide ROUTE or DEFER. Never ASK again.

    answer=None means skip or timeout: no evidence arrived, so the prior is
    kept, exactly as the (1 - rho) branch of R_ask assumes. An explicit
    "unknown" (or an answer outside the option list) is evidence and is
    applied through theta; it does not resolve a contradiction on the slot.
    """
    prior = np.asarray(inp.probs, dtype=np.float64)
    posterior = prior
    remaining = inp.contradicted_critical
    if answer is not None:
        values = inp.theta.values[slot]
        if answer not in values:
            answer = UNKNOWN_ANSWER
        p_answer, post = bayes_update(prior, inp.theta.theta(slot))
        idx = values.index(answer)
        if p_answer[idx] > 0:
            posterior = post[idx]
        if answer != UNKNOWN_ANSWER:
            remaining = inp.contradicted_critical - {slot}
    updated = GateInput(
        probs=posterior,
        conformal=inp.conformal,
        costs=inp.costs,
        theta=inp.theta,
        channel=inp.channel,
        askable_slots=(),
        contradicted_critical=frozenset(remaining),
        tau_hat=inp.tau_hat,
        no_ask_holdout=True,
    )
    return decide(updated)


__all__ = [
    "MAX_ROUTABLE_SET_SIZE",
    "ChannelCosts",
    "CostMatrix",
    "GateInput",
    "GateOutput",
    "SlotRisk",
    "ThetaTable",
    "ask_risk",
    "bayes_update",
    "decide",
    "finalize_after_answer",
    "route_risk",
]
