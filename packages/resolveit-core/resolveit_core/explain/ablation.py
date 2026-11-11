"""NumPy team head over [pooled vector || frame features] and slot-ablation evidence.

The head lives outside the ONNX graph so that ablating a slot costs one small
matrix product. An attribution is the measured drop in the top team's
probability when that slot is removed from the head's input: it describes
what the head actually used, not a story told after the fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from resolveit_core.calibrate.conformal_selective import softmax
from resolveit_core.schemas import SLOTS, Slot

FloatArray = NDArray[np.float64]


class FrameEncoder:
    """Per slot: one-hot over known values, plus a 'no value' indicator."""

    def __init__(self, vocab: Mapping[Slot, Sequence[str]]) -> None:
        self.vocab: dict[Slot, tuple[str, ...]] = {s: tuple(vocab.get(s, ())) for s in SLOTS}
        self._offset: dict[Slot, int] = {}
        pos = 0
        for slot in SLOTS:
            self._offset[slot] = pos
            pos += len(self.vocab[slot]) + 1
        self.dim = pos

    def index(self, slot: Slot, value: str | None) -> int:
        """Feature index of a slot value; value=None gives the 'no value' indicator."""
        vals = self.vocab[slot]
        return self._offset[slot] + (len(vals) if value is None else vals.index(value))

    def encode(self, values: Mapping[Slot, str]) -> FloatArray:
        out = np.zeros(self.dim, dtype=np.float64)
        for slot in SLOTS:
            base, vals = self._offset[slot], self.vocab[slot]
            v = values.get(slot)
            if v is not None and v in vals:
                out[base + vals.index(v)] = 1.0
            else:
                out[base + len(vals)] = 1.0
        return out


@dataclass(frozen=True, slots=True)
class Attribution:
    slot: Slot
    value: str
    delta_p: float


@dataclass(frozen=True, slots=True)
class LinearTeamHead:
    weights: FloatArray  # (n_teams, pooled_dim + encoder.dim)
    bias: FloatArray  # (n_teams,)
    encoder: FrameEncoder
    pooled_dim: int

    def __post_init__(self) -> None:
        if self.weights.shape != (self.bias.shape[0], self.pooled_dim + self.encoder.dim):
            raise ValueError("head weights do not match pooled_dim + frame feature dim")

    def logits(self, pooled: FloatArray, values: Mapping[Slot, str]) -> FloatArray:
        if pooled.shape != (self.pooled_dim,):
            raise ValueError("pooled vector has the wrong size")
        x = np.concatenate([pooled, self.encoder.encode(values)])
        out: FloatArray = self.weights @ x + self.bias
        return out

    def probs(self, pooled: FloatArray, values: Mapping[Slot, str], temperature: float) -> FloatArray:
        return softmax(self.logits(pooled, values), temperature)

    def attributions(
        self, pooled: FloatArray, values: Mapping[Slot, str], temperature: float
    ) -> tuple[Attribution, ...]:
        """Drop in the top team's probability when each filled slot is ablated, largest first."""
        full = self.probs(pooled, values, temperature)
        top = int(np.argmax(full))
        out: list[Attribution] = []
        for slot, value in values.items():
            reduced = {s: v for s, v in values.items() if s is not slot}
            ablated = self.probs(pooled, reduced, temperature)
            out.append(Attribution(slot, value, float(full[top] - ablated[top])))
        out.sort(key=lambda a: a.delta_p, reverse=True)
        return tuple(out)


__all__ = ["Attribution", "FrameEncoder", "LinearTeamHead"]
