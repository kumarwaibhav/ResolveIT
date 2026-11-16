"""Deterministic synthetic text with genuine offsets, not human annotations.

Each incident group has English, Hindi and Hinglish variants in exactly one split.
Template-family overlap is disclosed; group/text disjointness does not establish
real-world generalization or semantic independence of generated templates.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from resolveit_core.schemas import SLOTS, TEAMS

SPLITS = ("train", "scaling", "calibration", "policy_selection", "risk_certification", "frozen_test")
COUNTS = (8, 2, 4, 2, 4, 2)
SERVICES = (
    "VPN",
    "SSO",
    "Outlook",
    "laptop",
    "licence",
    "database",
    "cloud",
    "security",
    "SAP",
    "HRMS",
    "CI/CD",
    "meeting room",
)
LOCALES = ("en", "hi", "hinglish")


def canonical_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def sample_weight(row: dict[str, Any]) -> float:
    source = row.get("label_source")
    if source in {"synthetic_seed", "llm_silver"}:
        return 0.3
    if source == "human_gold" and row.get("verified_human_adjudication") is True:
        return 1.0
    raise ValueError("Unsupported or unverified annotation provenance")


def make_row(split: str, team: int, group_index: int, locale: str) -> dict[str, Any]:
    group = f"seed-v1/{split}/{team}/{group_index}"
    tag = hashlib.sha256(group.encode()).hexdigest()[:10]
    intros = {"en": "Incident report", "hi": "समस्या रिपोर्ट", "hinglish": "IT dikkat report"}
    fields = {
        "en": (
            SERVICES[team],
            "office gateway",
            "connection fails",
            "whole floor",
            "this morning",
            "intermittent",
            "production",
            f"ERR_{tag.upper()}",
            "recent update",
            "support analyst Pune",
            "urgent",
        ),
        "hi": (
            SERVICES[team],
            "कार्यालय गेटवे",
            "कनेक्शन विफल है",
            "पूरा विभाग",
            "आज सुबह",
            "बार बार",
            "उत्पादन प्रणाली",
            f"ERR_{tag.upper()}",
            "नया अपडेट",
            "सपोर्ट कर्मचारी पुणे",
            "बहुत जरूरी",
        ),
        "hinglish": (
            SERVICES[team],
            "office gateway",
            "connection nahi chal raha",
            "poori team",
            "aaj subah",
            "baar baar",
            "production system",
            f"ERR_{tag.upper()}",
            "naya update",
            "support analyst Pune",
            "jaldi chahiye",
        ),
    }[locale]
    text = f"{intros[locale]} {tag}: "
    spans: dict[str, list[list[int]]] = {}
    for slot, value in zip(SLOTS, fields, strict=True):
        if slot.value == "user_role_location":
            value += " my name is Synthetic Tester EMP1000 phone 9000000000 IP 10.0.0.1"
        text += f"{slot.value}: "
        start = len(text)
        text += value
        spans[slot.value] = [[start, len(text)]]
        text += "; "
    segments = [[0, len(text)]]
    if group_index % 3 == 0:
        start = len(text)
        text += {
            "en": "Separate issue: printer also fails.",
            "hi": "अलग समस्या: प्रिंटर भी नहीं चलता।",
            "hinglish": "Alag issue: printer bhi nahi chalta.",
        }[locale]
        segments.append([start, len(text)])
    return {
        "group_id": group,
        "split": split,
        "locale": locale,
        "text": text,
        "team": TEAMS[team].value,
        "label_source": "synthetic_seed",
        "spans": spans,
        "segments": segments,
        "generator": "resolveit-template-v1",
    }


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, str] = {}
    hashes: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for row in rows:
        split = row["split"]
        if split not in SPLITS or row["locale"] not in LOCALES or row["team"] not in TEAMS:
            raise ValueError("Invalid split, locale or team")
        sample_weight(row)
        group, digest = row["group_id"], canonical_hash(row["text"])
        if group in groups and groups[group] != split:
            raise ValueError("Incident group crosses split boundary")
        if digest in hashes:
            raise ValueError("Duplicate normalized text, including within a split")
        groups[group], hashes[digest] = split, split
        for spans in row["spans"].values():
            for start, end in spans:
                if not 0 <= start < end <= len(row["text"]):
                    raise ValueError("Invalid raw span")
        counts[split] += 1
    if set(counts) != set(SPLITS):
        raise ValueError("All six splits required")
    return {
        "n_rows": len(rows),
        "n_groups": len(groups),
        "split_counts": dict(counts),
        "normalized_text_duplicates": 0,
        "cross_split_groups": 0,
        "label_source": "synthetic_seed",
        "template_family_overlap": True,
        "human_gold_rows": 0,
        "dataset_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
    }


def generate(path: Path) -> dict[str, Any]:
    rows = [
        make_row(split, team, group, locale)
        for split, count in zip(SPLITS, COUNTS, strict=True)
        for team in range(len(TEAMS))
        for group in range(count)
        for locale in LOCALES
    ]
    report = audit_rows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    path.with_suffix(".audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit_rows(rows)
    return rows
