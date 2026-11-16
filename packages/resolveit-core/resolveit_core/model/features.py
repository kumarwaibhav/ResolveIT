"""Team-head features: encoder pooled vector, security flag, rule-frame one-hots.

One definition, imported by both the bundle builder and the API, so the
features a bundle was calibrated on are exactly the features it is served.
Frame values come from the raw-first rule engine, never from gold spans.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from resolveit_core.explain.ablation import FrameEncoder, LinearTeamHead
from resolveit_core.schemas import SLOTS, IncidentFrame, Slot

FloatArray = NDArray[np.float64]
STATED = "stated"
POOLED_WIDTH = 768
FEATURE_VERSION = "pooled768+security1+rule_frame_v1"

FRAME_VOCAB: dict[Slot, tuple[str, ...]] = {
    Slot.SERVICE: (
        "vpn", "wifi", "sso", "password", "email", "teams", "laptop", "printer",
        "licence", "database", "cloud", "sap", "hrms", "cicd", "meeting_room",
    ),
    Slot.SCOPE: ("single_user", "department_wide", "org_wide"),
    Slot.FREQUENCY: ("constant", "intermittent", "recurring", "first_time"),
    Slot.URGENCY: ("high", "low"),
}


def frame_encoder() -> FrameEncoder:
    return FrameEncoder({slot: FRAME_VOCAB.get(slot, (STATED,)) for slot in SLOTS})


def head_values(frame: IncidentFrame) -> dict[Slot, str]:
    """Every value the rules found, AMBIGUOUS included; slots without a vocabulary become 'stated'."""
    return {
        s.slot: (s.value if s.slot in FRAME_VOCAB else STATED) for s in frame.slots if s.value is not None
    }


def head_input(pooled: FloatArray, security_trigger: bool) -> FloatArray:
    if pooled.shape != (POOLED_WIDTH,):
        raise ValueError("pooled vector has the wrong width")
    return np.concatenate([np.asarray(pooled, dtype=np.float64), [float(security_trigger)]])


def feature_row(pooled: FloatArray, security_trigger: bool, values: Mapping[Slot, str]) -> FloatArray:
    return np.concatenate([head_input(pooled, security_trigger), frame_encoder().encode(values)])


def fold_standardised_head(
    weights: FloatArray, bias: FloatArray, mean: FloatArray, scale: FloatArray
) -> LinearTeamHead:
    """Turn logits = ((x - mean) / scale) @ W + b into one affine LinearTeamHead."""
    w = np.asarray(weights, dtype=np.float64)
    folded = (w / scale[:, None]).T
    offset = np.asarray(bias, dtype=np.float64) - (mean / scale) @ w
    return LinearTeamHead(folded, offset, frame_encoder(), POOLED_WIDTH + 1)


__all__ = [
    "FEATURE_VERSION",
    "FRAME_VOCAB",
    "POOLED_WIDTH",
    "STATED",
    "feature_row",
    "fold_standardised_head",
    "frame_encoder",
    "head_input",
    "head_values",
]
