"""Piecewise offset maps: raw code points <-> NFKC-normalised <-> PII-masked <-> tokens.

All offsets are Unicode code points except where a name says utf16.
Spans are half-open [start, end).

A map is a list of segments. An identity segment maps characters one to one.
An atomic segment maps a whole source range to a whole target range (a
normalised cluster or a PII placeholder); any position inside it resolves to
the full range, so a highlight never cuts a cluster or a placeholder.
"""

from __future__ import annotations

import bisect
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class Segment:
    src_start: int
    src_end: int
    dst_start: int
    dst_end: int
    atomic: bool


@dataclass(frozen=True, slots=True)
class Replacement:
    """Replace text[start:end] with `text`."""

    start: int
    end: int
    text: str


class OffsetMap:
    """Monotone alignment between a source string and a target string."""

    __slots__ = ("_dst_starts", "_src_starts", "dst_len", "segments", "src_len")

    def __init__(self, segments: Sequence[Segment], src_len: int, dst_len: int) -> None:
        self.segments: tuple[Segment, ...] = tuple(segments)
        self.src_len = src_len
        self.dst_len = dst_len
        self._validate()
        self._src_starts = [s.src_start for s in self.segments]
        self._dst_starts = [s.dst_start for s in self.segments]

    def _validate(self) -> None:
        src, dst = 0, 0
        for seg in self.segments:
            if seg.src_start != src or seg.dst_start != dst:
                raise ValueError("segments must be contiguous and ordered")
            if seg.src_end < seg.src_start or seg.dst_end < seg.dst_start:
                raise ValueError("negative segment")
            if not seg.atomic and seg.src_end - seg.src_start != seg.dst_end - seg.dst_start:
                raise ValueError("identity segment must preserve length")
            src, dst = seg.src_end, seg.dst_end
        if src != self.src_len or dst != self.dst_len:
            raise ValueError("segments do not cover both strings")

    @classmethod
    def identity(cls, length: int) -> OffsetMap:
        segs = [Segment(0, length, 0, length, False)] if length else []
        return cls(segs, length, length)

    def _locate(self, starts: list[int], pos: int) -> int:
        return max(bisect.bisect_right(starts, pos) - 1, 0)

    def _seg_for_dst(self, pos: int) -> Segment:
        """Segment whose non-empty dst range contains pos."""
        i = self._locate(self._dst_starts, pos)
        while i > 0 and self.segments[i].dst_end <= pos:  # pragma: no cover - defensive
            i -= 1
        while i < len(self.segments) - 1 and self.segments[i].dst_end <= pos:
            i += 1
        while self.segments[i].dst_end == self.segments[i].dst_start and i < len(self.segments) - 1:
            i += 1
        return self.segments[i]

    def _seg_for_src(self, pos: int) -> Segment:
        i = self._locate(self._src_starts, pos)
        while i < len(self.segments) - 1 and self.segments[i].src_end <= pos:
            i += 1
        return self.segments[i]

    def to_src(self, dst_start: int, dst_end: int) -> tuple[int, int]:
        """Smallest source span that covers target span [dst_start, dst_end)."""
        self._check(dst_start, dst_end, self.dst_len)
        if not self.segments:
            return (0, 0)
        if dst_start == dst_end:
            p = self._point_to_src(dst_start)
            return (p, p)
        first = self._seg_for_dst(dst_start)
        last = self._seg_for_dst(dst_end - 1)
        s = first.src_start if first.atomic else first.src_start + (dst_start - first.dst_start)
        e = last.src_end if last.atomic else last.src_start + (dst_end - last.dst_start)
        return (s, e)

    def to_dst(self, src_start: int, src_end: int) -> tuple[int, int]:
        """Smallest target span that covers source span [src_start, src_end)."""
        self._check(src_start, src_end, self.src_len)
        if not self.segments:
            return (0, 0)
        if src_start == src_end:
            p = self._point_to_dst(src_start)
            return (p, p)
        first = self._seg_for_src(src_start)
        last = self._seg_for_src(src_end - 1)
        s = first.dst_start if first.atomic else first.dst_start + (src_start - first.src_start)
        e = last.dst_end if last.atomic else last.dst_start + (src_end - last.src_start)
        return (s, e)

    def _point_to_src(self, pos: int) -> int:
        if pos >= self.dst_len:
            return self.src_len
        seg = self._seg_for_dst(pos)
        return seg.src_start if seg.atomic else seg.src_start + (pos - seg.dst_start)

    def _point_to_dst(self, pos: int) -> int:
        if pos >= self.src_len:
            return self.dst_len
        seg = self._seg_for_src(pos)
        return seg.dst_start if seg.atomic else seg.dst_start + (pos - seg.src_start)

    @staticmethod
    def _check(start: int, end: int, length: int) -> None:
        if not 0 <= start <= end <= length:
            raise ValueError(f"span [{start}, {end}) outside [0, {length}]")

    def is_identity_span_dst(self, dst_start: int, dst_end: int) -> bool:
        """True if every target character in the span maps one to one."""
        if dst_start == dst_end:
            return True
        i = self._locate(self._dst_starts, dst_start)
        while i < len(self.segments) and self.segments[i].dst_start < dst_end:
            seg = self.segments[i]
            if seg.atomic and seg.dst_end > dst_start and seg.dst_end > seg.dst_start:
                return False
            i += 1
        return True


def _merge_identity(segments: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for seg in segments:
        if seg.src_start == seg.src_end and seg.dst_start == seg.dst_end:
            continue
        if out and not seg.atomic and not out[-1].atomic:
            prev = out[-1]
            out[-1] = Segment(prev.src_start, seg.src_end, prev.dst_start, seg.dst_end, False)
        else:
            out.append(seg)
    return out


def _clusters(raw: str) -> list[tuple[int, int]]:
    """Split into the smallest pieces whose NFKC forms concatenate to NFKC(raw)."""
    n = len(raw)
    base: list[tuple[int, int]] = []
    i = 0
    while i < n:
        j = i + 1
        while j < n and unicodedata.combining(raw[j]) != 0:
            j += 1
        base.append((i, j))
        i = j
    merged: list[tuple[int, int]] = []
    for start, end in base:
        if merged:
            ps, pe = merged[-1]
            left, right = raw[ps:pe], raw[start:end]
            joined = unicodedata.normalize("NFKC", left + right)
            if joined != unicodedata.normalize("NFKC", left) + unicodedata.normalize("NFKC", right):
                merged[-1] = (ps, end)
                continue
        merged.append((start, end))
    return merged


def normalize_nfkc(raw: str) -> tuple[str, OffsetMap]:
    """NFKC-normalise and return the raw -> normalised map."""
    parts: list[str] = []
    segs: list[Segment] = []
    dst = 0
    for start, end in _clusters(raw):
        piece = raw[start:end]
        norm = unicodedata.normalize("NFKC", piece)
        segs.append(Segment(start, end, dst, dst + len(norm), norm != piece))
        parts.append(norm)
        dst += len(norm)
    return "".join(parts), OffsetMap(_merge_identity(segs), len(raw), dst)


def apply_replacements(text: str, replacements: Sequence[Replacement]) -> tuple[str, OffsetMap]:
    """Apply non-overlapping replacements and return the text -> replaced map."""
    ordered = sorted(replacements, key=lambda r: r.start)
    parts: list[str] = []
    segs: list[Segment] = []
    src, dst = 0, 0
    for rep in ordered:
        if rep.start < src or rep.end < rep.start or rep.end > len(text):
            raise ValueError("replacements overlap or fall outside the text")
        if rep.start > src:
            gap = rep.start - src
            segs.append(Segment(src, rep.start, dst, dst + gap, False))
            parts.append(text[src : rep.start])
            dst += gap
        segs.append(Segment(rep.start, rep.end, dst, dst + len(rep.text), True))
        parts.append(rep.text)
        dst += len(rep.text)
        src = rep.end
    if src < len(text):
        gap = len(text) - src
        segs.append(Segment(src, len(text), dst, dst + gap, False))
        parts.append(text[src:])
        dst += gap
    return "".join(parts), OffsetMap(_merge_identity(segs), len(text), dst)


class OffsetChain:
    """raw -> ... -> final, as an ordered list of maps."""

    __slots__ = ("maps",)

    def __init__(self, maps: Sequence[OffsetMap]) -> None:
        for a, b in pairwise(maps):
            if a.dst_len != b.src_len:
                raise ValueError("chain lengths do not line up")
        self.maps: tuple[OffsetMap, ...] = tuple(maps)

    def to_raw(self, start: int, end: int) -> tuple[int, int]:
        for m in reversed(self.maps):
            start, end = m.to_src(start, end)
        return (start, end)

    def from_raw(self, start: int, end: int) -> tuple[int, int]:
        for m in self.maps:
            start, end = m.to_dst(start, end)
        return (start, end)

    def token_span_to_raw(
        self, token_offsets: Sequence[tuple[int, int]], tok_start: int, tok_end: int
    ) -> tuple[int, int]:
        """Map tokens [tok_start, tok_end) to raw. token_offsets index the final text."""
        if not 0 <= tok_start < tok_end <= len(token_offsets):
            raise ValueError("token span outside sequence")
        return self.to_raw(token_offsets[tok_start][0], token_offsets[tok_end - 1][1])


class Utf16Index:
    """Convert code-point offsets to UTF-16 code-unit offsets and back for one string."""

    __slots__ = ("_prefix",)

    def __init__(self, text: str) -> None:
        prefix = [0]
        for ch in text:
            prefix.append(prefix[-1] + (2 if ord(ch) > 0xFFFF else 1))
        self._prefix = prefix

    def to_utf16(self, cp_offset: int) -> int:
        return self._prefix[cp_offset]

    def span_to_utf16(self, start: int, end: int) -> tuple[int, int]:
        return (self._prefix[start], self._prefix[end])

    def to_code_point(self, utf16_offset: int) -> int:
        """Inverse; an offset inside a surrogate pair snaps to the start of that character."""
        if not 0 <= utf16_offset <= self._prefix[-1]:
            raise ValueError("utf16 offset outside string")
        return bisect.bisect_right(self._prefix, utf16_offset) - 1


__all__ = [
    "OffsetChain",
    "OffsetMap",
    "Replacement",
    "Segment",
    "Utf16Index",
    "apply_replacements",
    "normalize_nfkc",
]
