from __future__ import annotations

import unicodedata

from hypothesis import given, settings
from hypothesis import strategies as st

from resolveit_core.masking.pii_shield import SPECIAL_TOKENS, mask_pii
from resolveit_core.offsets.offset_map import (
    OffsetChain,
    OffsetMap,
    Replacement,
    Utf16Index,
    apply_replacements,
    normalize_nfkc,
)

ALPHABET = st.one_of(
    st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    st.characters(min_codepoint=0x0900, max_codepoint=0x097F),  # Devanagari
    st.characters(min_codepoint=0x1F300, max_codepoint=0x1FAFF),  # emoji
    st.characters(min_codepoint=0x0300, max_codepoint=0x036F),  # combining marks
    st.characters(min_codepoint=0xFF01, max_codepoint=0xFF5E),  # fullwidth forms
    st.characters(min_codepoint=0x1100, max_codepoint=0x11FF),  # Hangul jamo
    st.sampled_from(
        [
            "\ufb01",
            "\u00b2",
            "\u00bd",
            "\u2122",
            "\u200d",
            "\ufe0f",
            "\u0958",
            "\u095b",
            "\u00c5",
            "\u00f1",
            "\u093c",
        ]
    ),
)
TEXT = st.text(alphabet=ALPHABET, max_size=60)
PII = st.sampled_from(
    ["a.b@corp.in", "9876543210", "+91 98765 43210", "10.0.12.7", "ABCDE1234F", "EMP-48213", "2363 4567 8902"]
)


@st.composite
def text_and_span(draw: st.DrawFn) -> tuple[str, int, int]:
    raw = draw(TEXT)
    norm_len = len(unicodedata.normalize("NFKC", raw))
    a = draw(st.integers(0, norm_len))
    b = draw(st.integers(a, norm_len))
    return raw, a, b


@settings(max_examples=10_000, deadline=None)
@given(text_and_span())
def test_nfkc_map_round_trip_10k(case: tuple[str, int, int]) -> None:
    raw, ds, de = case
    norm, omap = normalize_nfkc(raw)
    assert norm == unicodedata.normalize("NFKC", raw)
    ss, se = omap.to_src(ds, de)
    assert 0 <= ss <= se <= len(raw)
    if omap.is_identity_span_dst(ds, de):
        assert raw[ss:se] == norm[ds:de]
    else:
        assert norm[ds:de] in unicodedata.normalize("NFKC", raw[ss:se])
    back_s, back_e = omap.to_dst(ss, se)
    assert back_s <= ds and (back_e >= de or ds == de)  # a caret inside an atomic unit snaps to its start


@settings(max_examples=2_000, deadline=None)
@given(st.lists(st.one_of(TEXT, PII), min_size=1, max_size=6), st.data())
def test_full_chain_evidence_equals_raw(parts: list[str], data: st.DataObject) -> None:
    raw = " ".join(parts)
    norm, m1 = normalize_nfkc(raw)
    res = mask_pii(norm)
    chain = OffsetChain([m1, res.offset_map])
    masked = res.masked_text
    a = data.draw(st.integers(0, len(masked)))
    b = data.draw(st.integers(a, len(masked)))
    rs, re_ = chain.to_raw(a, b)
    assert 0 <= rs <= re_ <= len(raw)
    ns, ne = res.offset_map.to_src(a, b)
    if res.offset_map.is_identity_span_dst(a, b) and m1.is_identity_span_dst(ns, ne):
        assert raw[rs:re_] == masked[a:b]
    fs, fe = chain.from_raw(rs, re_)
    assert fs <= a and (fe >= b or a == b)


def test_placeholder_maps_to_whole_identifier() -> None:
    raw = "मेरा फोन 9876543210 है 😀 and VPN down"
    norm, m1 = normalize_nfkc(raw)
    res = mask_pii(norm)
    chain = OffsetChain([m1, res.offset_map])
    tok = "<PHONE_IN>"
    i = res.masked_text.index(tok)
    for a, b in [(i, i + len(tok)), (i + 2, i + 3), (i + len(tok) - 1, i + len(tok))]:
        rs, re_ = chain.to_raw(a, b)
        assert raw[rs:re_] == "9876543210"
    j = res.masked_text.index("VPN")
    rs, re_ = chain.to_raw(j, j + 3)
    assert raw[rs:re_] == "VPN"
    assert tok in SPECIAL_TOKENS


def test_token_span_to_raw() -> None:
    raw = "ｅｒｒｏｒ 0x80070005 on vpn"
    norm, m1 = normalize_nfkc(raw)
    res = mask_pii(norm)
    chain = OffsetChain([m1, res.offset_map])
    words = res.masked_text.split(" ")
    offsets, pos = [], 0
    for w in words:
        offsets.append((pos, pos + len(w)))
        pos += len(w) + 1
    rs, re_ = chain.token_span_to_raw(offsets, 1, 2)
    assert raw[rs:re_] == "0x80070005"
    rs, re_ = chain.token_span_to_raw(offsets, 0, 1)
    assert raw[rs:re_] == "ｅｒｒｏｒ"


@settings(max_examples=2_000, deadline=None)
@given(TEXT)
def test_utf16_matches_browser_units(text: str) -> None:
    idx = Utf16Index(text)
    for cp in range(len(text) + 1):
        expected = len(text[:cp].encode("utf-16-le")) // 2
        assert idx.to_utf16(cp) == expected
        assert idx.to_code_point(expected) == cp


def test_utf16_emoji_shift_and_snap() -> None:
    text = "a😀bक"
    idx = Utf16Index(text)
    assert idx.span_to_utf16(2, 3) == (3, 4)
    assert idx.to_code_point(2) == 1  # inside the surrogate pair snaps to the emoji start


def test_replacements_reject_overlap_and_validate() -> None:
    import pytest

    with pytest.raises(ValueError):
        apply_replacements("abcdef", [Replacement(0, 3, "X"), Replacement(2, 4, "Y")])
    with pytest.raises(ValueError):
        OffsetMap([], 3, 3)
    text, omap = apply_replacements("abcdef", [Replacement(2, 4, "")])
    assert text == "abef" and omap.to_src(1, 3) == (1, 5)
    assert OffsetMap.identity(0).to_src(0, 0) == (0, 0)
