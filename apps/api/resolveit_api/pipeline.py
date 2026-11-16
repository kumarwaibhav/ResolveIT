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
    experiment_assignment,
    finalize_after_answer,
    posterior_after_answer,
)
from resolveit_core.masking.pii_shield import MaskResult, mask_pii
from resolveit_core.model.features import head_input
from resolveit_core.model.features import head_values as trained_head_values
from resolveit_core.offsets.offset_map import normalize_nfkc
from resolveit_core.rules.engine import RuleResult, run_rules
from resolveit_core.schemas import (
    ASKABLE_STATES,
    TEAMS,
    Action,
    Channel,
    ConformalResult,
    Decision,
    DeferReason,
    IncidentFrame,
    QuestionRisk,
    Slot,
    SlotAttribution,
    Team,
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


def _head_part(bundle: Bundle, masked_text: str, security_trigger: bool) -> np.ndarray:
    """Non-frame head input: the INT8 encoder vector for trained bundles, the rule flag otherwise."""
    if bundle.encoder is None:
        return _pooled(security_trigger)
    return head_input(bundle.encoder(masked_text), security_trigger)


def _to_decision(
    out: GateOutput,
    probs: np.ndarray,
    bundle: Bundle,
    holdout: bool,
    attributions: tuple[SlotAttribution, ...],
    post_answer: bool = False,
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
        tau_hat=None
        if post_answer
        else bundle.queue_tau_hat.get(TEAMS.index(recommended))
        if bundle.queue_tau_hat is not None
        else bundle.tau_hat,
        question_risks=tuple(
            QuestionRisk(slot=r.slot, r_after=r.r_after, r_ask=r.r_ask) for r in out.slot_risks
        ),
        no_ask_holdout=holdout,
        attributions=attributions,
    )


def _gate_input(
    probs: np.ndarray,
    frame: IncidentFrame,
    bundle: Bundle,
    costs: ChannelCosts,
    holdout: bool,
    exploration_key: str | None = None,
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
        queue_tau_hat=bundle.queue_tau_hat,
        answer_queue_tau_hat=bundle.answer_queue_tau_hat,
        no_ask_holdout=holdout,
        exploration_key=exploration_key,
        critical_missing_slots=frozenset(
            s.slot for s in frame.slots if s.slot in CRITICAL_SLOTS and s.state in ASKABLE_STATES
        ),
    )


def _attributions(bundle: Bundle, frame: IncidentFrame, part: np.ndarray) -> tuple[SlotAttribution, ...]:
    values = _head_values(bundle, frame)
    return tuple(
        SlotAttribution(slot=a.slot, value=a.value, delta_p=a.delta_p)
        for a in bundle.head.attributions(part, values, bundle.temperature)
    )


def _head_values(bundle: Bundle, frame: IncidentFrame) -> dict[Slot, str]:
    """Trained bundles use the exact frame features they were calibrated on.

    Rule bundles feed only unambiguous values; an AMBIGUOUS slot is treated as not yet known.
    """
    if bundle.encoder is not None:
        return trained_head_values(frame)
    return {s.slot: s.value for s in frame.slots if s.value is not None and s.state not in ASKABLE_STATES}


def evaluate(
    raw_text: str,
    received_at: datetime,
    tenant_timezone: str,
    bundle: Bundle,
    costs: ChannelCosts,
    holdout: bool,
    exploration_key: str | None = None,
) -> Evaluation:
    rules = run_rules(raw_text, received_at, tenant_timezone)
    normalised, _ = normalize_nfkc(raw_text)
    mask = mask_pii(normalised)
    frame = frame_from_rules(rules)
    part = _head_part(bundle, mask.masked_text, rules.security_trigger)
    probs = bundle.head.probs(part, _head_values(bundle, frame), bundle.temperature)
    holdout = holdout or (experiment_assignment(exploration_key)[0] if exploration_key else False)
    out = decide(_gate_input(probs, frame, bundle, costs, holdout, exploration_key))
    decision = _to_decision(out, probs, bundle, holdout, _attributions(bundle, frame, part))
    if rules.security_trigger:
        decision = _security_escalation(decision)
    return Evaluation(rules, mask, frame, decision)


def _security_escalation(decision: Decision) -> Decision:
    """A security trigger bypasses ordinary routing: no question, no model-certified auto-route.

    The ticket goes to a human on the security queue at once. The probabilities stay on record
    for audit but are not presented as a calibrated security verdict.
    """
    return decision.model_copy(
        update={
            "action": Action.DEFER,
            "team": None,
            "ask_slot": None,
            "question_risks": (),
            "defer_reason": DeferReason.SECURITY_ESCALATION,
            "recommended_team": Team.SECURITY,
        }
    )


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
        # The server restarted on a different bundle: the stored probabilities and thresholds
        # no longer belong together, so hand the ticket to a human instead of failing forever.
        return initial.model_copy(
            update={
                "action": Action.DEFER,
                "team": None,
                "ask_slot": None,
                "defer_reason": DeferReason.BUNDLE_CHANGED,
            }
        )
    probs = np.array(initial.probs, dtype=np.float64)
    out = finalize_after_answer(_gate_input(probs, frame, bundle, costs, True), slot, answer)
    posterior, _ = posterior_after_answer(probs, bundle.theta, slot, answer)
    return _to_decision(
        out,
        posterior,
        bundle,
        initial.no_ask_holdout,
        # The encoder vector is not stored, so trained bundles keep the evidence computed at intake.
        initial.attributions
        if bundle.encoder is not None
        else _attributions(bundle, frame, _pooled(security_trigger)),
        post_answer=True,
    )


__all__ = ["CHANNEL_DEFAULTS", "CRITICAL_SLOTS", "Evaluation", "channel_costs", "evaluate", "finalize"]
