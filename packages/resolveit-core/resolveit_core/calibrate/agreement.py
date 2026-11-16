"""Observed nominal agreement; undefined agreement stays None, never invented."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def cohens_kappa(first: Sequence[str], second: Sequence[str]) -> float | None:
    """Cohen's kappa for paired, independently supplied nominal labels."""
    if len(first) != len(second):
        raise ValueError("paired annotations must align")
    if not first:
        return None
    n = len(first)
    left, right = Counter(first), Counter(second)
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / n
    chance = sum(left[k] * right[k] for k in left.keys() | right.keys()) / n**2
    return None if chance == 1 else (observed - chance) / (1 - chance)


def krippendorff_alpha(rows: Sequence[Sequence[str | None]]) -> float | None:
    """Nominal alpha with missing labels and variable annotator counts.

    Each row is one item. Items with fewer than two labels carry no pairwise
    information and are excluded from both observed and expected coincidence.
    """
    units = [[v for v in row if v is not None] for row in rows]
    units = [row for row in units if len(row) >= 2]
    counts: Counter[str] = Counter(v for row in units for v in row)
    n = sum(counts.values())
    if n < 2:
        return None
    observed = sum(
        sum(a != b for a in row for b in row) / (len(row) - 1)
        for row in units
    ) / n
    expected = (n * n - sum(c * c for c in counts.values())) / (n * (n - 1))
    return None if expected == 0 else 1 - observed / expected
