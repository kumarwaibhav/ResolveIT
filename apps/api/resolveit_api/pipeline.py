"""Text -> rules -> mask -> frame -> probabilities -> gate. Pure functions, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from resolveit_core.frame.merger import frame_from_rules
from resolveit_core.gate.bayes_evsi import (
    ChannelCosts,
    GateInput,
    GateOutput,
    decide,
    finalize_after_answer,
    posterior_after_answer,
)
from resolveit_core.masking.pii_shield import MaskResult, mask_pii
from resolveit_core.offsets.offset_map import normalize_nfkc
from resolveit_core.rules.engine import RuleResult, run_rules
from resolveit_core.schemas import (
    ASKABLE_STATES,
    TEAMS,
    Channel,
    ConformalResult,
    Decision,
    IncidentFrame,
    QuestionRisk,
    Slot,
    SlotAttribution,
)

from resolveit_api.bundles import POOLED_DIM, Bundle

CRITICAL_SLOTS: frozenset[Slot] = frozenset({Slot.SERVICE, Slot.SYMPTOM})

# (minutes one question costs, extra minutes lost when it goes unanswered). Defaults until measured.
CHANNEL_DEFAULTS: dict[Channel, tuple[float, float]] = {
    Channel.WEB: (1.0, 10.0),
    Channel.CHAT: (2.0, 15.0),
    Channel.AGENT: (0.5, 2.0),
    Channel.EMAIL: (30.0, 240.0),
    Channel.ITSM: (30.0, 240.0),
}


@dataclass(frozen=True, slots=True)
class Evaluation:
    rules: RuleResult
    mask: MaskResult
    frame: IncidentFrame
    decision: Decision


def channel_costs(channel: Channel, asks: int, answers: int) -> ChannelCosts:
    c_ask, c_ghost = CHANNEL_DEFAULTS[channel]
    return ChannelCosts(c_ask=c_ask, c_ghost=c_ghost, asks=asks, answers=answers)


def _pooled(security_trigger: bool) -> np.ndarray:
    out = np.zeros(POOLED_DIM)
    out[0] = float(security_trigger)
    return out


def _to_decision(
    out: GateOutput,
    probs: np.ndarray,
    bundle: Bundle,
    holdout: bool,
    attributions: tuple[SlotAttribution, ...],
) -> Decision:
    recommended = TEAMS[int(np.argmin(probs @ bundle.costs.delay))]
    return Decision(
        action=out.action,
        bundle_id=bundle.bundle_id,
        probs=tuple(float(p) for p in probs),
        conformal=ConformalResult(
            teams=tuple(TEAMS[i] for i in out.conformal_set),
            alpha=bundle.conformal.alpha,
            class_conditional=tuple(bool(b) for b in bundle.conformal.class_conditional),
        ),
        team=TEAMS[out.team] if out.team is not None else None,
        recommended_team=recommended,
        ask_slot=out.ask_slot,
        defer_reason=out.defer_reason,
        r_route=None if out.r_route == float("inf") else out.r_route,
        r_now=out.r_now,
        c_def=bundle.costs.c_def,
        tau_hat=bundle.tau_hat,
        question_risks=tuple(
            QuestionRisk(slot=r.slot, r_after=r.r_after, r_ask=r.r_ask) for r in out.slot_risks
        ),
        no_ask_holdout=holdout,
        attributions=attributions,
    )


def _gate_input(
    probs: np.ndarray, frame: IncidentFrame, bundle: Bundle, costs: ChannelCosts, holdout: bool
) -> GateInput:
    askable = tuple(
        s.slot for s in frame.slots if s.state in ASKABLE_STATES and s.slot in bundle.theta.values
    )
    return GateInput(
        probs=probs,
        conformal=bundle.conformal,
        costs=bundle.costs,
        theta=bundle.theta,
        channel=costs,
        askable_slots=askable,
        contradicted_critical=frozenset(),  # rules-only frames cannot be CONTRADICTED
        tau_hat=bundle.tau_hat,
        no_ask_holdout=holdout,
    )


def _attributions(bundle: Bundle, frame: IncidentFrame, security: bool) -> tuple[SlotAttribution, ...]:
    values = _head_values(frame)
    return tuple(
        SlotAttribution(slot=a.slot, value=a.value, delta_p=a.delta_p)
        for a in bundle.head.attributions(_pooled(security), values, bundle.temperature)
    )


def _head_values(frame: IncidentFrame) -> dict[Slot, str]:
    """Only unambiguous values feed the head; an AMBIGUOUS slot is treated as not yet known."""
    return {s.slot: s.value for s in frame.slots if s.value is not None and s.state not in ASKABLE_STATES}


def evaluate(
    raw_text: str,
    received_at: datetime,
    tenant_timezone: str,
    bundle: Bundle,
    costs: ChannelCosts,
    holdout: bool,
) -> Evaluation:
    rules = run_rules(raw_text, received_at, tenant_timezone)
    normalised, _ = normalize_nfkc(raw_text)
    mask = mask_pii(normalised)
    frame = frame_from_rules(rules)
    probs = bundle.head.probs(_pooled(rules.security_trigger), _head_values(frame), bundle.temperature)
    out = decide(_gate_input(probs, frame, bundle, costs, holdout))
    decision = _to_decision(out, probs, bundle, holdout, _attributions(bundle, frame, rules.security_trigger))
    return Evaluation(rules, mask, frame, decision)


def finalize(
    initial: Decision,
    frame: IncidentFrame,
    slot: Slot,
    answer: str | None,
    bundle: Bundle,
    costs: ChannelCosts,
    security_trigger: bool,
) -> Decision:
    """Close the clarification with the bundle that asked the question."""
    if initial.bundle_id != bundle.bundle_id:
        raise ValueError("answer must be evaluated with the bundle that asked the question")
    probs = np.array(initial.probs, dtype=np.float64)
    out = finalize_after_answer(_gate_input(probs, frame, bundle, costs, True), slot, answer)
    posterior, _ = posterior_after_answer(probs, bundle.theta, slot, answer)
    return _to_decision(
        out, posterior, bundle, initial.no_ask_holdout, _attributions(bundle, frame, security_trigger)
    )


__all__ = ["CHANNEL_DEFAULTS", "CRITICAL_SLOTS", "Evaluation", "channel_costs", "evaluate", "finalize"]
