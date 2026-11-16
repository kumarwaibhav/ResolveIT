"""Synthetic natural-language tickets for fitting the external head and its calibration.

Generated text, not human annotation: label_source stays "synthetic_seed".
The trained encoder is not retrained on these rows. They exist because the
encoder's seed templates ("service: VPN; component: ...") do not resemble
typed tickets, so the head, temperature, conformal sets and routing
certificates are fitted on generated free text instead.

Three kinds of rows:
  clear     names a system the rules recognise, so the team is identifiable
  security  describes phishing / compromise without naming a routed system
  vague     no system named; the label is drawn at random and is NOT
            recoverable from the text. service_key records what an honest
            reporter would answer if asked, for post-answer certification.
Every row carries a unique desk tag so no text repeats across splits.
"""

from __future__ import annotations

import hashlib
import json
import random
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from resolveit_core.schemas import TEAMS, Team

GENERATOR = "resolveit-freetext-v2"
LOCALES = ("en", "hi", "hinglish")

# service_key -> (team, en phrases, hi phrases, hinglish phrases); phrases match the rule lexicon.
SERVICES: dict[str, tuple[Team, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "vpn": (Team.NETWORK, ("VPN", "the GlobalProtect VPN"), ("वीपीएन",), ("VPN", "office VPN")),
    "wifi": (Team.NETWORK, ("office wifi", "the Wi-Fi"), ("वाई-फाई",), ("wifi", "office ka wifi")),
    "sso": (Team.IDENTITY_ACCESS, ("SSO login", "Okta"), ("SSO लॉगिन",), ("SSO login", "Okta")),
    "password": (Team.IDENTITY_ACCESS, ("my password reset", "the password"), ("पासवर्ड",), ("password",)),
    "email": (Team.EMAIL_COLLAB, ("Outlook", "my mailbox"), ("ईमेल",), ("Outlook", "mailbox")),
    "teams": (Team.EMAIL_COLLAB, ("MS Teams", "Microsoft Teams"), ("MS Teams",), ("MS Teams",)),
    "laptop": (Team.HARDWARE_ENDPOINT, ("my laptop", "the ThinkPad"), ("लैपटॉप",), ("laptop", "mera laptop")),
    "printer": (Team.HARDWARE_ENDPOINT, ("the printer", "the print queue"), ("प्रिंटर",), ("printer",)),
    "licence": (Team.SOFTWARE_LICENSING, ("my licence", "the activation key"), ("लाइसेंस",), ("licence",)),
    "database": (Team.DATABASE, ("the Postgres database", "the MySQL server"), ("डेटाबेस",), ("database",)),
    "cloud": (
        Team.CLOUD_INFRA,
        ("the AWS console", "our EC2 instance", "the Kubernetes cluster"),
        ("AWS console",),
        ("AWS console", "Kubernetes cluster"),
    ),
    "sap": (Team.ERP_FINANCE, ("SAP", "Tally"), ("SAP",), ("SAP", "Tally")),
    "hrms": (Team.HR_SYSTEMS, ("Workday", "my payslip"), ("payslip",), ("payslip", "HRMS")),
    "cicd": (
        Team.DEVOPS_CICD,
        ("the Jenkins pipeline", "GitHub Actions"),
        ("Jenkins pipeline",),
        ("Jenkins pipeline", "build agent"),
    ),
    "meeting_room": (
        Team.FACILITIES_AV,
        ("the projector", "the conference room screen"),
        ("प्रोजेक्टर",),
        ("projector", "meeting room"),
    ),
}

SYMPTOM = {
    "en": (
        "is not working",
        "keeps disconnecting",
        "is very slow",
        "shows an error",
        "won't open",
        "crashes every time",
    ),
    "hi": ("काम नहीं कर रहा", "बार बार बंद हो रहा है", "बहुत धीमा है", "एरर दिखा रहा है", "खुल नहीं रहा"),
    "hinglish": (
        "kaam nahi kar raha",
        "baar baar disconnect ho raha hai",
        "bahut slow hai",
        "error de raha hai",
        "khul nahi raha",
    ),
}
SCOPE = {
    "en": ("", "for the whole floor", "for everyone", "only me"),
    "hi": ("", "पूरी टीम के लिए", "सबका"),
    "hinglish": ("", "poori team ka", "sabka", "sirf mera"),
}
WHEN = {
    "en": ("", "since this morning", "since yesterday", "3 hours ago", "again"),
    "hi": ("", "सुबह से", "फिर से"),
    "hinglish": ("", "subah se", "phir se", "kal se"),
}
URGENT = {
    "en": ("", "urgent", "no rush"),
    "hi": ("", "बहुत जरूरी", "जल्दी"),
    "hinglish": ("", "jaldi dekho", "urgent hai"),
}
VAGUE = {
    "en": (
        "it stopped working",
        "nothing is loading",
        "my system is acting weird",
        "I can't get my work done",
        "something is broken",
    ),
    "hi": ("कुछ भी काम नहीं कर रहा", "सिस्टम ठीक से नहीं चल रहा", "कुछ गड़बड़ है"),
    "hinglish": (
        "kuch kaam nahi kar raha",
        "system ajeeb chal raha hai",
        "kuch toot gaya hai",
        "mera kaam ruk gaya hai",
    ),
}
SECURITY = {
    "en": (
        "I clicked a suspicious link and now my account got hacked",
        "ransomware popup on my screen",
        "I think there is malware on my machine",
        "someone has unauthorized access to my account",
    ),
    "hi": ("मैंने एक संदिग्ध लिंक पर क्लिक किया, अकाउंट हैक हो गया", "मेरी मशीन पर फिशिंग हमला हुआ"),
    "hinglish": (
        "maine suspicious link pe click kiya, mera account hack ho gaya",
        "lagta hai malware aa gaya",
        "kisi ne unauthorized access le liya",
    ),
}
SECURITY_KEY = "unknown"  # no routable service value describes a security incident


def canonical(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _join(parts: list[str]) -> str:
    return " ".join(p for p in parts if p).strip()


def _row(rng: random.Random, kind: str, team: Team, locale: str, split: str, index: int) -> dict[str, Any]:
    desk = f"desk {rng.choice('ABCDEFGH')}-{rng.randint(100, 999)}"
    if kind == "clear":
        keys = [k for k, v in SERVICES.items() if v[0] is team]
        key = rng.choice(keys)
        phrases = SERVICES[key][1 + LOCALES.index(locale)]
        body = _join(
            [
                rng.choice(phrases),
                rng.choice(SYMPTOM[locale]),
                rng.choice(SCOPE[locale]),
                rng.choice(WHEN[locale]),
            ]
        )
    elif kind == "security":
        key = SECURITY_KEY
        body = _join([rng.choice(SECURITY[locale]), rng.choice(WHEN[locale])])
    else:
        keys = [k for k, v in SERVICES.items() if v[0] is team]
        key = rng.choice(keys) if keys else SECURITY_KEY
        body = _join([rng.choice(VAGUE[locale]), rng.choice(SCOPE[locale]), rng.choice(WHEN[locale])])
    urgency = rng.choice(URGENT[locale])
    text = f"{body}, {urgency} ({desk})" if urgency else f"{body} ({desk})"
    return {
        "group_id": f"{GENERATOR}/{split}/{team.value}/{index}",
        "split": split,
        "locale": locale,
        "text": text[0].upper() + text[1:] if locale != "hi" else text,
        "team": team.value,
        "kind": kind,
        "service_key": key,
        "label_source": "synthetic_seed",
        "generator": GENERATOR,
    }


# rows per team per split, and the share of vague rows in that split
PLAN: dict[str, tuple[int, float]] = {
    "head_train": (150, 0.25),
    "scaling": (30, 0.25),
    "calibration": (170, 0.25),
    "risk_certification": (280, 0.25),
    "answer_certification": (320, 1.0),
    "policy_selection": (10, 0.25),
    "frozen_test": (50, 0.25),
}


def generate(seed: int = 20261116) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for split, (per_team, vague_share) in PLAN.items():
        for team in TEAMS:
            made = 0
            attempts = 0
            while made < per_team:
                attempts += 1
                if attempts > per_team * 200:
                    raise RuntimeError("generator cannot produce enough unique rows")
                if team is Team.SECURITY:
                    kind = "vague" if rng.random() < vague_share else "security"
                else:
                    kind = "vague" if rng.random() < vague_share else "clear"
                locale = LOCALES[(made + LOCALES.index("en")) % 3]
                row = _row(rng, kind, team, locale, split, made)
                key = canonical(row["text"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
                made += 1
    return rows


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    texts = Counter(canonical(r["text"]) for r in rows)
    groups = Counter(r["group_id"] for r in rows)
    return {
        "generator": GENERATOR,
        "n_rows": len(rows),
        "split_counts": dict(Counter(r["split"] for r in rows)),
        "kind_counts": dict(Counter(r["kind"] for r in rows)),
        "locale_counts": dict(Counter(r["locale"] for r in rows)),
        "duplicate_texts": sum(c - 1 for c in texts.values()),
        "duplicate_groups": sum(c - 1 for c in groups.values()),
        "label_source": "synthetic_seed",
        "human_gold_rows": 0,
        "vague_labels_recoverable_from_text": False,
        "template_family_overlap": True,
        "dataset_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
    }


def write(path: Path, seed: int = 20261116) -> dict[str, Any]:
    rows = generate(seed)
    report = audit(rows)
    if report["duplicate_texts"] or report["duplicate_groups"]:
        raise RuntimeError("generated duplicates")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    path.with_suffix(".audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
