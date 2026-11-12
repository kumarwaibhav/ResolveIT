"""Build the 11-slot frame from rule evidence.

This is the rules-only path used until a trained extractor exists. The
model merge (PRESENT / CONTRADICTED from rule value vs model value) is added
with the ONNX bundle; CONTRADICTED cannot occur here because there is only
one source.
"""

from __future__ import annotations

from resolveit_core.rules.engine import RuleHit, RuleResult
from resolveit_core.schemas import (
    SLOTS,
    EpistemicState,
    Evidence,
    IncidentFrame,
    Slot,
    SlotValue,
    SourceLayer,
    Span,
)


def _slot_value(slot: Slot, hits: tuple[RuleHit, ...]) -> SlotValue:
    if not hits:
        return SlotValue(slot=slot, state=EpistemicState.MISSING)
    evidence = tuple(
        Evidence(
            span=Span(start=h.start, end=h.end), source=SourceLayer.RULE, confidence=1.0, rule_id=h.rule_id
        )
        for h in hits
    )
    distinct = list(dict.fromkeys(h.value for h in hits))
    unclear = len(distinct) > 1 or any(h.ambiguous for h in hits)
    state = EpistemicState.AMBIGUOUS if unclear else EpistemicState.PRESENT
    return SlotValue(slot=slot, state=state, value=distinct[0], evidence=evidence)


def frame_from_rules(result: RuleResult) -> IncidentFrame:
    return IncidentFrame(slots=tuple(_slot_value(s, result.by_slot(s)) for s in SLOTS))


def apply_answer(frame: IncidentFrame, slot: Slot, value: str, source: SourceLayer) -> IncidentFrame:
    """Return a new frame with `slot` set from a clarification answer."""
    updated = SlotValue(
        slot=slot,
        state=EpistemicState.PRESENT,
        value=value,
        evidence=(*frame.get(slot).evidence,),
    )
    _ = source  # recorded on the question row; evidence spans stay those found in the text
    return IncidentFrame(slots=tuple(updated if s.slot is slot else s for s in frame.slots))


__all__ = ["apply_answer", "frame_from_rules"]
