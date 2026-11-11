from __future__ import annotations

from datetime import UTC, datetime

from resolveit_core.masking.pii_shield import mask_pii, verhoeff_check_digit, verhoeff_valid
from resolveit_core.rules.engine import run_rules
from resolveit_core.schemas import Slot

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)  # 11:30 IST, a Thursday


def aadhaar(body11: str) -> str:
    return body11 + verhoeff_check_digit(body11)


def test_verhoeff_reference_vector() -> None:
    assert verhoeff_check_digit("236") == "3"
    assert verhoeff_valid("2363") and not verhoeff_valid("2364")


def test_verhoeff_catches_every_single_digit_error_and_adjacent_swap() -> None:
    good = aadhaar("49912345678")
    assert verhoeff_valid(good)
    for i, ch in enumerate(good):
        for d in "0123456789":
            if d != ch:
                assert not verhoeff_valid(good[:i] + d + good[i + 1 :])
    for i in range(len(good) - 1):
        if good[i] != good[i + 1]:
            assert not verhoeff_valid(good[:i] + good[i + 1] + good[i] + good[i + 2 :])


def test_valid_aadhaar_masked_invalid_left_alone() -> None:
    good = aadhaar("49912345678")
    spaced = f"{good[:4]} {good[4:8]} {good[8:]}"
    bad = good[:-1] + str((int(good[-1]) + 1) % 10)
    res = mask_pii(f"id {spaced} and asset 3{bad[1:]}")
    assert "<AADHAAR>" in res.masked_text and spaced not in res.masked_text
    assert res.entities[0].identifier == good
    assert mask_pii(f"asset tag {bad}").masked_text == f"asset tag {bad}"


def test_error_codes_and_ticket_ids_survive_masking() -> None:
    text = "INC0012345 failed with 0x80070005, ERR_CONNECTION_RESET, KB5031356, PROJ-4821, Event ID 4625"
    assert mask_pii(text).masked_text == text


def test_structured_identifiers_masked() -> None:
    text = (
        "Regards, Rahul Sharma EMP-48213 rahul.sharma@corp.in +91 98765 43210 "
        "PAN ABCDE1234F host 10.0.12.7 not 999.1.1.1"
    )
    out = mask_pii(text).masked_text
    for token in ("<USER_NAME>", "<EMP_ID>", "<EMAIL>", "<PHONE_IN>", "<PAN>", "<IP_ADDR>"):
        assert token in out
    for leak in ("Rahul", "48213", "corp.in", "98765", "ABCDE1234F", "10.0.12.7"):
        assert leak not in out
    assert "999.1.1.1" in out


def test_known_names_from_tenant_directory() -> None:
    from resolveit_core.masking.pii_shield import MaskerConfig

    out = mask_pii("priya ka laptop slow hai", MaskerConfig(known_names=frozenset({"Priya"})))
    assert out.masked_text == "<USER_NAME> ka laptop slow hai"


def test_rules_error_code_service_recurrence_scope_urgency() -> None:
    raw = "VPN is down again for the whole floor since morning, error 0x80070005, urgent"
    r = run_rules(raw, NOW, "Asia/Kolkata")
    got = {(h.slot, h.value) for h in r.hits}
    assert (Slot.SERVICE, "vpn") in got
    assert (Slot.FREQUENCY, "recurring") in got
    assert (Slot.SCOPE, "department_wide") in got
    assert (Slot.URGENCY, "high") in got
    assert (Slot.ERROR_CODE, "0x80070005") in got
    assert (Slot.START_TIME, "2026-11-12T09:00+05:30") in got
    for h in r.hits:
        assert 0 <= h.start < h.end <= len(raw)
    code = next(h for h in r.hits if h.slot is Slot.ERROR_CODE)
    assert raw[code.start : code.end] == "0x80070005"
    assert not r.security_trigger


def test_rules_hinglish_and_devanagari() -> None:
    r = run_rules("mera laptop phir se slow hai aur VPN bhi nahi chal raha, jaldi dekho", NOW, "Asia/Kolkata")
    got = {(h.slot, h.value) for h in r.hits}
    assert {
        (Slot.SERVICE, "laptop"),
        (Slot.SERVICE, "vpn"),
        (Slot.FREQUENCY, "recurring"),
        (Slot.URGENCY, "high"),
    } <= got
    r2 = run_rules("वीपीएन फिर से बंद है, सबका", NOW, "Asia/Kolkata")
    got2 = {(h.slot, h.value) for h in r2.hits}
    assert {(Slot.SERVICE, "vpn"), (Slot.FREQUENCY, "recurring"), (Slot.SCOPE, "org_wide")} <= got2


def test_kal_is_ambiguous_never_guessed() -> None:
    r = run_rules("kal se wifi nahi chal raha", NOW, "Asia/Kolkata")
    t = r.by_slot(Slot.START_TIME)
    assert len(t) == 1 and t[0].ambiguous and t[0].value == "kal se"


def test_relative_time_uses_tenant_timezone() -> None:
    late = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)  # already 13 Nov in India
    r = run_rules("broken since yesterday, also 3 hours ago, since Monday", late, "Asia/Kolkata")
    vals = {h.rule_id: h.value for h in r.by_slot(Slot.START_TIME)}
    assert vals["time.yesterday"] == "2026-11-12T00:00+05:30"
    assert vals["time.ago"] == "2026-11-12T22:30+05:30"
    assert vals["time.since_weekday"] == "2026-11-09T00:00+05:30"


def test_security_trigger() -> None:
    r = run_rules("I clicked on a link in a suspicious email and my account got hacked", NOW, "Asia/Kolkata")
    assert r.security_trigger and len(r.security_spans) >= 2
    assert run_rules("mera account hack ho gaya", NOW, "Asia/Kolkata").security_trigger


def test_naive_datetime_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        run_rules("x", datetime(2026, 1, 1), "Asia/Kolkata")
