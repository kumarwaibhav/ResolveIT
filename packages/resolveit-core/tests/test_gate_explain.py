from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from resolveit_core.calibrate.conformal_selective import ConformalCalibrator
from resolveit_core.explain.ablation import FrameEncoder, LinearTeamHead
from resolveit_core.gate.bayes_evsi import (
    ChannelCosts,
    CostMatrix,
    GateInput,
    ThetaTable,
    bayes_update,
    decide,
    finalize_after_answer,
)
from resolveit_core.schemas import N_TEAMS, SLOTS, UNKNOWN_ANSWER, Action, DeferReason, Slot

K = N_TEAMS
VALUES = {Slot.SERVICE: ["vpn", "email", "laptop"], Slot.SCOPE: ["single_user", "org_wide"]}


def calibrator(threshold: float = 0.8) -> ConformalCalibrator:
    return ConformalCalibrator(
        0.10, np.full(K, threshold), np.ones(K, dtype=bool), threshold, np.full(K, 150, dtype=np.int64)
    )


def theta_informative() -> ThetaTable:
    t = ThetaTable(VALUES)
    for _ in range(200):
        t.add(Slot.SERVICE, "vpn", 0)
        t.add(Slot.SERVICE, "email", 2)
        t.add(Slot.SERVICE, "laptop", 3)
    for team in range(K):
        for _ in range(20):
            t.add(Slot.SCOPE, "single_user", team)
            t.add(Slot.SCOPE, "org_wide", team)
    return t


def probs(**mass: float) -> np.ndarray:
    p = np.zeros(K)
    for k, v in mass.items():
        p[int(k[1:])] = v
    rest = 1.0 - p.sum()
    p[p == 0] = rest / (p == 0).sum()
    return p


def gate_input(p: np.ndarray, **kw: object) -> GateInput:
    base: dict[str, object] = dict(
        probs=p,
        conformal=calibrator(),
        costs=CostMatrix.uniform(240.0, 45.0),
        theta=theta_informative(),
        channel=ChannelCosts(c_ask=2.0, c_ghost=10.0, asks=98, answers=69),
        askable_slots=(Slot.SERVICE, Slot.SCOPE),
        contradicted_critical=frozenset(),
        tau_hat=0.80,
    )
    base.update(kw)
    return GateInput(**base)  # type: ignore[arg-type]


@settings(max_examples=500, deadline=None)
@given(
    st.lists(st.floats(0.01, 10.0), min_size=K, max_size=K),
    st.lists(st.lists(st.floats(0.0, 50.0), min_size=K, max_size=K), min_size=4, max_size=4),
    st.floats(0.1, 100.0),
)
def test_bayes_update_is_coherent(raw_p: list[float], counts: list[list[float]], kappa: float) -> None:
    p = np.array(raw_p) / np.sum(raw_p)
    t = ThetaTable({Slot.SERVICE: ["a", "b", "c"]}, kappa=kappa)
    t.counts[Slot.SERVICE] = np.array(counts)
    theta = t.theta(Slot.SERVICE)
    assert np.allclose(theta.sum(axis=0), 1.0, atol=1e-12)
    p_answer, post = bayes_update(p, theta)
    assert abs(p_answer.sum() - 1.0) < 1e-9
    assert np.max(np.abs((p_answer[:, None] * post).sum(axis=0) - p)) < 1e-9


def test_theta_cold_start_is_uniform_and_has_unknown() -> None:
    t = ThetaTable(VALUES)
    assert t.values[Slot.SERVICE][-1] == UNKNOWN_ANSWER
    assert np.allclose(t.theta(Slot.SERVICE), 0.25)
    full = ThetaTable({s: [f"v{i}" for i in range(8)] for s in SLOTS})
    assert full.n_cells() == 11 * 9 * 12


def test_confident_ticket_routes() -> None:
    out = decide(gate_input(probs(k0=0.97)))
    assert out.action is Action.ROUTE and out.team == 0
    assert math.isclose(out.r_route, 0.03 * 240.0) and out.r_now == out.r_route


def test_empty_set_never_routes_but_may_still_ask() -> None:
    flat = np.full(K, 1.0 / K)
    out = decide(gate_input(flat, askable_slots=()))
    assert out.action is Action.DEFER and out.defer_reason is DeferReason.NO_CONFORMING_TEAM
    assert out.conformal_set == () and out.r_route == math.inf
    asked = decide(gate_input(probs(k0=0.34, k2=0.33, k3=0.33), conformal=calibrator(0.5)))
    assert asked.conformal_set == () and asked.action is Action.ASK and asked.ask_slot is Slot.SERVICE


def test_informative_question_is_asked_and_holdout_suppresses_it() -> None:
    p = probs(k0=0.45, k2=0.45)
    out = decide(gate_input(p))
    assert out.action is Action.ASK and out.ask_slot is Slot.SERVICE
    by_slot = {r.slot: r for r in out.slot_risks}
    assert by_slot[Slot.SERVICE].r_after < by_slot[Slot.SCOPE].r_after
    assert math.isclose(by_slot[Slot.SCOPE].r_after, out.r_now)  # uninformative slot changes nothing
    held = decide(gate_input(p, no_ask_holdout=True))
    assert held.action is Action.DEFER and held.defer_reason is DeferReason.RISK_ABOVE_DEFER_COST


def test_low_response_rate_stops_asking() -> None:
    p = probs(k0=0.45, k2=0.45)
    ghosted = ChannelCosts(c_ask=2.0, c_ghost=600.0, asks=200, answers=4)
    assert ghosted.rho < 0.03
    assert decide(gate_input(p, channel=ghosted)).action is Action.DEFER
    assert ChannelCosts(1.0, 1.0).rho == 0.5


def test_shadow_mode_never_routes() -> None:
    out = decide(gate_input(probs(k0=0.97), tau_hat=None, askable_slots=()))
    assert out.action is Action.DEFER and out.defer_reason is DeferReason.SHADOW_MODE
    assert out.r_route == math.inf


def test_large_set_and_critical_contradiction_forbid_route() -> None:
    wide = decide(gate_input(probs(k0=0.9), conformal=calibrator(0.999), askable_slots=()))
    assert wide.action is Action.DEFER and wide.defer_reason is DeferReason.SET_TOO_LARGE
    blocked = decide(
        gate_input(probs(k0=0.97), contradicted_critical=frozenset({Slot.SYMPTOM}), askable_slots=())
    )
    assert blocked.action is Action.DEFER and blocked.defer_reason is DeferReason.CRITICAL_CONTRADICTION


def test_answer_then_route_skip_then_defer_never_ask_twice() -> None:
    inp = gate_input(probs(k0=0.45, k2=0.45))
    answered = finalize_after_answer(inp, Slot.SERVICE, "vpn")
    assert answered.action is Action.ROUTE and answered.team == 0
    for skipped in (None, UNKNOWN_ANSWER, "something not in the option list"):
        out = finalize_after_answer(inp, Slot.SERVICE, skipped)
        assert out.action is Action.DEFER
    assert np.allclose(finalize_after_answer(inp, Slot.SERVICE, None).r_now, decide(inp).r_now)
    assert answered.slot_risks == ()


def test_cost_matrix_validation_and_asymmetric_costs_change_the_route() -> None:
    import pytest

    with pytest.raises(ValueError):
        CostMatrix(np.ones((K, K)), 45.0)
    delay = np.full((K, K), 60.0)
    np.fill_diagonal(delay, 0.0)
    delay[7, :] = 5000.0  # a Security incident sent anywhere else is very expensive
    delay[7, 7] = 0.0
    p = probs(k0=0.80, k7=0.19)
    out = decide(
        gate_input(
            p, costs=CostMatrix(delay, 5000.0), tau_hat=0.5, conformal=calibrator(0.9), askable_slots=()
        )
    )
    assert out.action is Action.ROUTE and out.team == 7
    assert CostMatrix.uniform(10, 5).scaled(2).delay[0, 1] == 20


def head() -> LinearTeamHead:
    enc = FrameEncoder({Slot.SERVICE: ["vpn", "email"], Slot.SCOPE: ["single_user", "org_wide"]})
    w = np.zeros((K, 4 + enc.dim))
    w[0, 4 + enc.index(Slot.SERVICE, "vpn")] = 4.0  # strongly
    w[0, 4 + enc.index(Slot.SCOPE, "org_wide")] = 0.5  # weakly
    w[2, 4 + enc.index(Slot.SERVICE, "email")] = 4.0
    return LinearTeamHead(w, np.zeros(K), enc, 4)


def test_ablation_ranks_the_slot_the_head_actually_used() -> None:
    h = head()
    values = {Slot.SERVICE: "vpn", Slot.SCOPE: "org_wide", Slot.URGENCY: "high"}
    pooled = np.zeros(4)
    attrs = h.attributions(pooled, values, temperature=1.0)
    assert [a.slot for a in attrs][:2] == [Slot.SERVICE, Slot.SCOPE]
    assert attrs[0].delta_p > attrs[1].delta_p > 0
    assert abs(attrs[2].delta_p) < 1e-12  # urgency has no vocabulary and no weight: zero effect
    full = h.probs(pooled, values, 1.0)
    without = h.probs(pooled, {Slot.SCOPE: "org_wide"}, 1.0)
    assert math.isclose(attrs[0].delta_p, full[0] - without[0])


def test_head_feeds_the_gate_end_to_end() -> None:
    h = head()
    p = h.probs(np.zeros(4), {Slot.SERVICE: "vpn", Slot.SCOPE: "org_wide"}, temperature=0.5)
    out = decide(gate_input(p, askable_slots=()))
    assert out.action is Action.ROUTE and out.team == 0
