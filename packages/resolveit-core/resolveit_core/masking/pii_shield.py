"""Checksum-validated PII masker.

Runs AFTER the rule engine has read the raw text. Works on NFKC-normalised
text and returns masked text plus the normalised -> masked OffsetMap.

Recall on free-text names is best effort; structured identifiers are the
part with a measurable guarantee (see tests and gate G2).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from resolveit_core.offsets.offset_map import OffsetMap, Replacement, apply_replacements


class PiiType(StrEnum):
    EMAIL = "<EMAIL>"
    AADHAAR = "<AADHAAR>"
    PAN = "<PAN>"
    IP_ADDR = "<IP_ADDR>"
    PHONE_IN = "<PHONE_IN>"
    EMP_ID = "<EMP_ID>"
    USER_NAME = "<USER_NAME>"


SPECIAL_TOKENS: tuple[str, ...] = tuple(t.value for t in PiiType)

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_valid(digits: str) -> bool:
    if not digits.isascii() or not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(digits: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


# Spans that look like identifiers but are incident evidence. Never masked.
_PROTECTED = (
    re.compile(r"0x[0-9A-Fa-f]{4,}"),
    re.compile(r"\b(?:INC|REQ|RITM|CHG|TASK|PRB|SCTASK)\d{5,}\b"),
    re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b"),
    re.compile(r"\bERR_[A-Z0-9_]+\b"),
    re.compile(r"\bKB\d{6,}\b"),
    re.compile(r"\b(?:Event\s+ID|event\s+id)\s*:?\s*\d{3,5}\b"),
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_AADHAAR = re.compile(r"(?<![\dA-Za-z])[2-9]\d{3}[ \-]?\d{4}[ \-]?\d{4}(?![\dA-Za-z])")
_PAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Za-z0-9])")
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_PHONE = re.compile(r"(?<![\dA-Za-z])(?:\+?91[ \-]?|0)?[6-9]\d{4}[ \-]?\d{5}(?![\dA-Za-z])")
_DEFAULT_EMP = re.compile(r"(?<![A-Za-z0-9])(?:EMP|emp|Emp)[\-_ ]?\d{4,8}(?![A-Za-z0-9])")
_NAME_WORD = r"[A-Z][a-z]+"
_NAME_CUES = re.compile(
    r"(?:\b(?:[Mm]y name is|[Rr]egards,?|[Tt]hanks,?|[Tt]hank you,?|[Mm]era naam|"
    r"Mr\.?|Mrs\.?|Ms\.?|Shri|Smt\.?|Dr\.?)\s+)"
    rf"({_NAME_WORD}(?:\s+{_NAME_WORD}){{0,2}})"
)


@dataclass(frozen=True, slots=True)
class PiiEntity:
    kind: PiiType
    start: int  # normalised-text code points
    end: int
    identifier: str  # canonical form for the blind index; never persist or log


@dataclass(frozen=True, slots=True)
class MaskResult:
    masked_text: str
    offset_map: OffsetMap  # normalised -> masked
    entities: tuple[PiiEntity, ...]


@dataclass(frozen=True, slots=True)
class MaskerConfig:
    employee_id_pattern: re.Pattern[str] = _DEFAULT_EMP
    known_names: frozenset[str] = frozenset()


def _valid_ipv4(text: str) -> bool:
    return all(p.isdigit() and int(p) <= 255 and (p == "0" or not p.startswith("0")) for p in text.split("."))


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _candidates(text: str, cfg: MaskerConfig) -> Iterable[PiiEntity]:
    for m in _EMAIL.finditer(text):
        yield PiiEntity(PiiType.EMAIL, m.start(), m.end(), m.group().lower())
    for m in _AADHAAR.finditer(text):
        d = _digits(m.group())
        if verhoeff_valid(d):
            yield PiiEntity(PiiType.AADHAAR, m.start(), m.end(), d)
    for m in _PAN.finditer(text):
        yield PiiEntity(PiiType.PAN, m.start(), m.end(), m.group())
    for m in _IPV4.finditer(text):
        if _valid_ipv4(m.group()):
            yield PiiEntity(PiiType.IP_ADDR, m.start(), m.end(), m.group())
    for m in _PHONE.finditer(text):
        yield PiiEntity(PiiType.PHONE_IN, m.start(), m.end(), _digits(m.group())[-10:])
    for m in cfg.employee_id_pattern.finditer(text):
        yield PiiEntity(PiiType.EMP_ID, m.start(), m.end(), _digits(m.group()))
    for m in _NAME_CUES.finditer(text):
        yield PiiEntity(PiiType.USER_NAME, m.start(1), m.end(1), m.group(1).lower())
    for name in sorted(cfg.known_names, key=len, reverse=True):
        if not name:
            continue
        for m in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", text, flags=re.IGNORECASE):
            yield PiiEntity(PiiType.USER_NAME, m.start(), m.end(), name.lower())


def protected_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for pat in _PROTECTED for m in pat.finditer(text)]


def _overlaps(a_start: int, a_end: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(a_start < e and s < a_end for s, e in spans)


def mask_pii(normalised_text: str, cfg: MaskerConfig | None = None) -> MaskResult:
    """Replace PII with typed special tokens. Earlier detector types win on overlap."""
    cfg = cfg or MaskerConfig()
    # The tenant's explicit employee-ID pattern outranks the generic KEY-123 protection.
    emp = [(m.start(), m.end()) for m in cfg.employee_id_pattern.finditer(normalised_text)]
    protected = [sp for sp in protected_spans(normalised_text) if not _overlaps(sp[0], sp[1], emp)]
    taken: list[tuple[int, int]] = []
    kept: list[PiiEntity] = []
    for ent in _candidates(normalised_text, cfg):
        if ent.start == ent.end:
            continue
        if _overlaps(ent.start, ent.end, protected) or _overlaps(ent.start, ent.end, taken):
            continue
        taken.append((ent.start, ent.end))
        kept.append(ent)
    kept.sort(key=lambda e: e.start)
    masked, omap = apply_replacements(
        normalised_text, [Replacement(e.start, e.end, e.kind.value) for e in kept]
    )
    return MaskResult(masked, omap, tuple(kept))


__all__ = [
    "SPECIAL_TOKENS",
    "MaskResult",
    "MaskerConfig",
    "PiiEntity",
    "PiiType",
    "mask_pii",
    "protected_spans",
    "verhoeff_check_digit",
    "verhoeff_valid",
]
