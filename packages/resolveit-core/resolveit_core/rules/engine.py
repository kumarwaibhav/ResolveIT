"""Deterministic rule layer. Runs in memory on RAW text, before any masking.

Every hit carries a raw code-point span so the UI can highlight it and so the
masker can never destroy it. English, Hindi (Devanagari) and romanised
Hinglish cues are matched by lexicon; no parser is involved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from resolveit_core.schemas import Slot


@dataclass(frozen=True, slots=True)
class RuleHit:
    slot: Slot
    value: str
    start: int
    end: int
    rule_id: str
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class RuleResult:
    hits: tuple[RuleHit, ...]
    security_trigger: bool
    security_spans: tuple[tuple[int, int], ...]

    def by_slot(self, slot: Slot) -> tuple[RuleHit, ...]:
        return tuple(h for h in self.hits if h.slot is slot)


_I = re.IGNORECASE

_ERROR_CODES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("err.hex", re.compile(r"0x[0-9A-Fa-f]{4,}")),
    ("err.chromium", re.compile(r"\bERR_[A-Z0-9_]+\b")),
    ("err.oracle", re.compile(r"\bORA-\d{5}\b")),
    ("err.event_id", re.compile(r"\bEvent\s+ID\s*:?\s*(\d{3,5})\b", _I)),
    ("err.http", re.compile(r"\b(?:HTTP|status|error)\s*(?:code)?\s*:?\s*([45]\d{2})\b", _I)),
    ("err.generic", re.compile(r"\berror\s+code\s*:?\s*([A-Za-z0-9_\-]{3,20})\b", _I)),
)

_SERVICES: tuple[tuple[str, str], ...] = (
    ("vpn", r"\b(?:vpn|globalprotect|anyconnect|forticlient)\b|वीपीएन"),
    ("wifi", r"\b(?:wi-?fi|wireless|wlan)\b|वाई-?फाई"),
    ("email", r"\b(?:outlook|e-?mail|mailbox|exchange|gmail)\b|ईमेल|मेल"),
    ("teams", r"\b(?:ms teams|microsoft teams|teams)\b"),
    ("laptop", r"\b(?:laptop|notebook|macbook|thinkpad)\b|लैपटॉप"),
    ("printer", r"\b(?:printer|print queue)\b|प्रिंटर"),
    ("sso", r"\b(?:sso|okta|azure ad|entra|single sign[- ]on|mfa|2fa)\b"),
    ("password", r"\b(?:password|passcode)\b|पासवर्ड"),
    ("sap", r"\b(?:sap|s/4hana|oracle ebs|tally)\b"),
    ("hrms", r"\b(?:workday|hrms|successfactors|darwinbox|payslip|payroll)\b"),
    ("database", r"\b(?:database|postgres|mysql|sql server|oracle db|mongodb)\b|डेटाबेस"),
    ("cloud", r"\b(?:aws|azure|gcp|ec2|s3 bucket|kubernetes|k8s)\b"),
    ("cicd", r"\b(?:jenkins|github actions|gitlab ci|pipeline|build agent|argo ?cd)\b"),
    ("licence", r"\b(?:licen[cs]e|subscription|activation key)\b|लाइसेंस"),
    ("meeting_room", r"\b(?:projector|conference room|meeting room|av system|zoom room)\b"),
)

_FREQUENCY: tuple[tuple[str, str], ...] = (
    ("recurring", r"\b(?:again|once again|keeps? (?:on )?\w+ing|every time|each time|repeatedly)\b"),
    (
        "recurring",
        r"\b(?:phir se|fir se|dobara|baar baar|bar bar|har baar|har bar)\b|फिर से|दोबारा|बार बार|हर बार",
    ),
    ("intermittent", r"\b(?:intermittent(?:ly)?|on and off|sometimes|randomly|kabhi kabhi)\b|कभी कभी"),
    ("constant", r"\b(?:always|constantly|all the time|continuously|hamesha|lagatar)\b|हमेशा|लगातार"),
    ("first_time", r"\b(?:first time|never happened before|pehli baar|pehli bar)\b|पहली बार"),
)

_URGENCY: tuple[tuple[str, str], ...] = (
    ("high", r"\b(?:urgent(?:ly)?|asap|immediately|critical|blocker|production (?:is )?down|p1|sev ?1)\b"),
    ("high", r"\b(?:jaldi|turant|abhi ke abhi|bahut zaroori|bahut jaruri)\b|जल्दी|तुरंत|बहुत ज़रूरी|बहुत जरूरी"),
    ("low", r"\b(?:whenever (?:you can|possible)|no rush|low priority|not urgent)\b"),
)

_SCOPE: tuple[tuple[str, str], ...] = (
    (
        "department_wide",
        r"\b(?:whole|entire) (?:floor|team|department|office)\b|\ball of us\b|\bpoor[ie] team\b|\bpoora (?:floor|office)\b|पूरी टीम|पूरा ऑफिस",
    ),
    (
        "org_wide",
        r"\b(?:everyone|everybody|all users|company[- ]wide|org[- ]wide|sabka|sab ka|sabhi)\b|सबका|सभी",
    ),
    ("single_user", r"\b(?:only me|just me|only my|sirf mera|sirf meri|sirf mere)\b|सिर्फ मेरा|सिर्फ मेरी"),
)

_SECURITY = re.compile(
    r"\b(?:phish(?:ing|ed)?|ransomware|malware|virus|trojan|data breach|breach(?:ed)?|"
    r"suspicious (?:link|e-?mail|attachment|login)|clicked (?:on )?(?:a |the )?(?:link|attachment)|"
    r"account (?:was |got |is )?(?:hacked|compromised)|password (?:was |got )?(?:leaked|stolen)|"
    r"unauthori[sz]ed access|hack ho gaya|hack ho gya|hack kar liya)\b|फ़िशिंग|फिशिंग|हैक",
    _I,
)

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

_T_AGO = re.compile(r"\b(\d{1,3})\s*(minute|min|hour|hr|day|week)s?\s+(?:ago|pehle|pahle)\b", _I)
_T_SINCE_DAY = re.compile(r"\bsince\s+(" + "|".join(_WEEKDAYS) + r")\b", _I)
_T_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?\b")
_T_MORNING = re.compile(r"\b(?:since (?:this )?morning|this morning|subah se|aaj subah)\b|सुबह से", _I)
_T_TODAY = re.compile(r"\b(?:since today|today|aaj se|aaj)\b|आज(?![\u0900-\u097F])", _I)
_T_YESTERDAY = re.compile(r"\b(?:since yesterday|yesterday)\b", _I)
_T_KAL = re.compile(r"\bkal(?: se)?\b|कल(?: से)?(?![\u0900-\u097F])", _I)
_T_LAST_WEEK = re.compile(r"\b(?:since last week|last week|pichhle hafte|pichle hafte)\b|पिछले हफ्ते", _I)

_UNIT = {
    "minute": "minutes",
    "min": "minutes",
    "hour": "hours",
    "hr": "hours",
    "day": "days",
    "week": "weeks",
}


def _lexicon(text: str, slot: Slot, table: tuple[tuple[str, str], ...], prefix: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for value, pattern in table:
        for m in re.finditer(pattern, text, flags=_I):
            hits.append(RuleHit(slot, value, m.start(), m.end(), f"{prefix}.{value}"))
    return hits


def _error_codes(text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    seen: list[tuple[int, int]] = []
    for rule_id, pat in _ERROR_CODES:
        for m in pat.finditer(text):
            g = 1 if pat.groups else 0
            s, e = m.start(g), m.end(g)
            if any(s < pe and ps < e for ps, pe in seen):
                continue
            seen.append((s, e))
            hits.append(RuleHit(Slot.ERROR_CODE, m.group(g), s, e, rule_id))
    return hits


def _start_times(text: str, now: datetime) -> list[RuleHit]:
    hits: list[RuleHit] = []

    def add(m: re.Match[str], when: datetime | None, rule: str, ambiguous: bool = False) -> None:
        value = when.isoformat(timespec="minutes") if when is not None else m.group()
        hits.append(RuleHit(Slot.START_TIME, value, m.start(), m.end(), rule, ambiguous))

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for m in _T_AGO.finditer(text):
        delta = timedelta(**{_UNIT[m.group(2).lower()]: int(m.group(1))})
        add(m, now - delta, "time.ago")
    for m in _T_SINCE_DAY.finditer(text):
        back = (now.weekday() - _WEEKDAYS.index(m.group(1).lower())) % 7 or 7
        add(m, midnight - timedelta(days=back), "time.since_weekday")
    for m in _T_ISO.finditer(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm = (int(m.group(4)), int(m.group(5))) if m.group(4) else (0, 0)
        try:
            add(m, datetime(y, mo, d, hh, mm, tzinfo=now.tzinfo), "time.iso")
        except ValueError:
            continue
    for m in _T_MORNING.finditer(text):
        add(m, midnight.replace(hour=9), "time.morning")
    for m in _T_YESTERDAY.finditer(text):
        add(m, midnight - timedelta(days=1), "time.yesterday")
    for m in _T_LAST_WEEK.finditer(text):
        add(m, midnight - timedelta(days=7), "time.last_week")
    for m in _T_KAL.finditer(text):
        # "kal" is yesterday or tomorrow. Never guess.
        add(m, None, "time.kal", ambiguous=True)
    covered = [(h.start, h.end) for h in hits]
    for m in _T_TODAY.finditer(text):
        if not any(m.start() < e and s < m.end() for s, e in covered):
            add(m, midnight, "time.today")
    return hits


def run_rules(raw_text: str, received_at: datetime, tenant_timezone: str) -> RuleResult:
    """Extract rule evidence from raw text.

    `received_at` must be timezone-aware. Relative times are resolved in the
    tenant's timezone.
    """
    if received_at.tzinfo is None:
        raise ValueError("received_at must be timezone-aware")
    now = received_at.astimezone(ZoneInfo(tenant_timezone))
    hits: list[RuleHit] = []
    hits += _error_codes(raw_text)
    hits += _lexicon(raw_text, Slot.SERVICE, _SERVICES, "svc")
    hits += _lexicon(raw_text, Slot.FREQUENCY, _FREQUENCY, "freq")
    hits += _lexicon(raw_text, Slot.URGENCY, _URGENCY, "urg")
    hits += _lexicon(raw_text, Slot.SCOPE, _SCOPE, "scope")
    hits += _start_times(raw_text, now)
    hits.sort(key=lambda h: (h.start, h.end, h.rule_id))
    sec = tuple((m.start(), m.end()) for m in _SECURITY.finditer(raw_text))
    return RuleResult(tuple(hits), bool(sec), sec)


__all__ = ["RuleHit", "RuleResult", "run_rules"]
