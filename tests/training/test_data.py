from __future__ import annotations

import copy
from pathlib import Path

import pytest

from training.data import SPLITS, audit_rows, generate, load, make_row, sample_weight


def test_generated_splits_and_offsets(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    report = generate(path)
    rows = load(path)
    assert report["n_rows"] == 792
    assert report["n_groups"] == 264
    assert set(report["split_counts"]) == set(SPLITS)
    assert {row["locale"] for row in rows} == {"en", "hi", "hinglish"}
    for row in rows:
        start, end = row["spans"]["service"][0]
        assert row["text"][start:end]
        assert sample_weight(row) == 0.3


def test_leakage_and_provenance_rejected(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    generate(path)
    rows = load(path)
    duplicate = copy.deepcopy(rows[0])
    duplicate["split"] = "frozen_test"
    with pytest.raises(ValueError, match="crosses split"):
        audit_rows([*rows, duplicate])
    duplicate["group_id"] = "different"
    with pytest.raises(ValueError, match="Duplicate"):
        audit_rows([*rows, duplicate])
    with pytest.raises(ValueError, match="unverified"):
        sample_weight({"label_source": "human_gold"})
    assert sample_weight({"label_source": "human_gold", "verified_human_adjudication": True}) == 1


def test_compound_segment_boundaries() -> None:
    row = make_row("train", 0, 0, "hi")
    assert len(row["segments"]) == 2
    assert row["segments"][0][1] == row["segments"][1][0]
