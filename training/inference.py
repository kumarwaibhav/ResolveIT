"""Shared text preparation, group sampling and external NumPy team-head features.

Frame features use raw-first rules at both training and inference, never oracle
gold spans. The ONNX BIO outputs are evaluated independently; production merger
integration remains explicit rather than feeding labels to the team head.
"""

from __future__ import annotations

import gc
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import onnxruntime as ort
from resolveit_core.frame.merger import frame_from_rules
from resolveit_core.masking.pii_shield import mask_pii
from resolveit_core.offsets.offset_map import normalize_nfkc
from resolveit_core.rules.engine import run_rules
from resolveit_core.schemas import SLOTS, TEAMS, Slot

FRAME_VOCAB = {
    "service": [
        "vpn",
        "wifi",
        "sso",
        "password",
        "email",
        "teams",
        "laptop",
        "printer",
        "licence",
        "database",
        "cloud",
        "sap",
        "hrms",
        "cicd",
        "meeting_room",
    ],
    "scope": ["single_user", "department_wide", "org_wide"],
    "frequency": ["constant", "intermittent", "recurring", "first_time"],
    "urgency": ["high", "low"],
}


def representatives(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    """One deterministic locale per group, selected without labels or predictions."""
    selected = []
    for row in rows:
        if row["split"] != split:
            continue
        target = int.from_bytes(hashlib.sha256(row["group_id"].encode()).digest()[:8]) % 3
        if row["locale"] == ("en", "hi", "hinglish")[target]:
            selected.append(row)
    return selected


def prepared_text(text: str) -> str:
    normalized, _ = normalize_nfkc(text)
    return mask_pii(normalized).masked_text


def frame_values(text: str) -> dict[Slot, str]:
    result = frame_from_rules(run_rules(text, datetime(2026, 11, 15, tzinfo=UTC), "Asia/Kolkata"))
    values: dict[Slot, str] = {}
    for slot in result.slots:
        if slot.value is not None:
            values[slot.slot] = slot.value if slot.slot.value in FRAME_VOCAB else "stated"
    return values


def frame_encoder() -> Any:
    from resolveit_core.explain.ablation import FrameEncoder

    return FrameEncoder({slot: FRAME_VOCAB.get(slot.value, ["stated"]) for slot in SLOTS})


def validate_external_data(path: Path) -> list[str]:
    """Reject escaped or unmanifested external ONNX tensors before ORT opens them."""
    import onnx

    root = path.parent.resolve(strict=True)
    manifest_path = root / "manifest.json"
    manifest_files = json.loads(manifest_path.read_text())["files"] if manifest_path.exists() else None
    model = onnx.load(str(path), load_external_data=False)
    references: set[str] = set()

    def tensor(item: Any) -> None:
        locations = [entry.value for entry in item.external_data if entry.key == "location"]
        if len(locations) > 1:
            raise ValueError("Duplicate external tensor locations")
        for location in locations:
            parts = location.split("/")
            if (
                not location
                or any(c in location for c in ("\\", ":", "\0"))
                or PurePosixPath(location).is_absolute()
                or any(p in {"", ".", ".."} for p in parts)
            ):
                raise ValueError("Unsafe ONNX external tensor path")
            target = root.joinpath(*parts)
            if any(p.is_symlink() or p.is_junction() for p in (target, *target.parents)):
                raise ValueError("ONNX tensor links forbidden")
            if not target.resolve(strict=True).is_relative_to(root) or not target.is_file():
                raise ValueError("ONNX external tensor escaped bundle")
            if manifest_files is not None and location not in manifest_files:
                raise ValueError("ONNX external tensor absent from manifest")
            references.add(location)

    def graph(item: Any) -> None:
        for value in item.initializer:
            tensor(value)
        for sparse in item.sparse_initializer:
            tensor(sparse.values)
            tensor(sparse.indices)
        for node in item.node:
            for attr in node.attribute:
                if attr.HasField("t"):
                    tensor(attr.t)
                for value in attr.tensors:
                    tensor(value)
                if attr.HasField("g"):
                    graph(attr.g)
                for subgraph in attr.graphs:
                    graph(subgraph)

    graph(model.graph)
    del model
    gc.collect()
    return sorted(references)


def session(path: Path, threads: int = 2) -> ort.InferenceSession:
    validate_external_data(path)
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def features(pooled: np.ndarray, texts: list[str]) -> np.ndarray:
    encoder = frame_encoder()
    frames = np.stack([encoder.encode(frame_values(text)) for text in texts])
    return np.concatenate([pooled.astype(np.float64), frames], axis=1)


def inputs(tokenizer: Any, texts: list[str], max_length: int = 192) -> dict[str, np.ndarray]:
    encoded = tokenizer(
        [prepared_text(text) for text in texts],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="np",
    )
    return {key: np.asarray(encoded[key], dtype=np.int64) for key in ("input_ids", "attention_mask")}


def labels(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[team.value for team in TEAMS].index(row["team"]) for row in rows], dtype=np.int64)


def head_logits(x: np.ndarray, head: Any) -> np.ndarray:
    return ((x - head["mean"]) / head["scale"]) @ head["weights"] + head["bias"]
