"""Measure the actual shipped pretrained encoder; never substitute fixture latency."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import psutil
from gpu_guard import ResourceGuard
from resolveit_core.frame.merger import frame_from_rules
from resolveit_core.model.features import feature_row, head_values
from resolveit_core.rules.engine import run_rules
from verify_bundle import verify_bundle

from training.inference import inputs, session


def head_logits(pooled: np.ndarray, text: str, head: Any) -> np.ndarray:
    """Serving feature path: pooled768 + security flag + rule-frame one-hots, folded linear head."""
    rules = run_rules(text, datetime.now(UTC), "Asia/Kolkata")
    row = feature_row(
        pooled[0].astype(np.float64), rules.security_trigger, head_values(frame_from_rules(rules))
    )
    return np.asarray(head["weights"] @ row + head["bias"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/release_candidate_bundle")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/training/pretrained_latency.json")
    parser.add_argument("--expected-id")
    args = parser.parse_args()
    guard = ResourceGuard()
    before = guard.checkpoint()
    manifest = json.loads((args.bundle / "manifest.json").read_text())
    verification = verify_bundle(args.bundle, args.expected_id or manifest["bundle_id"])
    report = json.loads((args.bundle / "report.json").read_text())
    if (
        report.get("pretrained_model_trained") is not True
        or report.get("base_model") != "microsoft/mdeberta-v3-base"
    ):
        raise ValueError("This gate requires the actual pretrained multilingual encoder")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.bundle / "tokenizer", local_files_only=True)
    threads = min(4, psutil.cpu_count(logical=False) or 1)
    process = psutil.Process()
    rss_before = process.memory_info().rss
    start = time.perf_counter()
    ort = session(args.bundle / "model_int8.onnx", threads)
    # Fully occupied fast path:128 actual nonpadding tokens, excluding tokenizer
    # time for the encoder receipt. Pipeline time is measured separately.
    sentence = "VPN connection stopped working this morning for the whole department. "
    encoded = tokenizer(sentence * 30, truncation=True, max_length=128, return_tensors="np")
    feed = {name: np.asarray(encoded[name], dtype=np.int64) for name in ("input_ids", "attention_mask")}
    if feed["input_ids"].shape != (1, 128) or int(feed["attention_mask"].sum()) != 128:
        raise ValueError("Latency input must contain128 actual tokens")
    ort.run(None, feed)
    cold = (time.perf_counter() - start) * 1000
    for i in range(200):
        if i % 20 == 0:
            guard.checkpoint()
        ort.run(None, feed)
    samples = []
    for i in range(200):
        if i % 20 == 0:
            guard.checkpoint()
        start = time.perf_counter_ns()
        ort.run(None, feed)
        samples.append((time.perf_counter_ns() - start) / 1e6)
    head = np.load(args.bundle / "linear_head.npz")
    text = "VPN is down this morning for the whole department, urgent."
    pipeline = []
    for _ in range(30):
        guard.checkpoint()
        start = time.perf_counter_ns()
        pooled = ort.run(["pooled"], inputs(tokenizer, [text], 128))[0]
        head_logits(pooled, text, head)
        pipeline.append((time.perf_counter_ns() - start) / 1e6)
    p50, p95 = np.quantile(samples, [0.5, 0.95]).tolist()
    receipt = {
        "bundle_id": verification["bundle_id"],
        "pretrained_model_trained": True,
        "fixture": False,
        "label_source": report["label_source"],
        "production_authorized": False,
        "base_model": report["base_model"],
        "revision": report["revision"],
        "intra_op_num_threads": threads,
        "inter_op_num_threads": 1,
        "sequence_length": 128,
        "batch_size": 1,
        "calibration_input_policy": "batch1_dynamic_padding_max192; never truncate long reports to128",
        "benchmark_scope": "128-token encoder engineering benchmark, not a separate risk certificate",
        "process_rss_mib": process.memory_info().rss / 2**20,
        "session_rss_increment_mib": (process.memory_info().rss - rss_before) / 2**20,
        "warmup_requests": 200,
        "timed_requests": 200,
        "load_and_first_ms": cold,
        "p50_ms": p50,
        "p95_ms": p95,
        "target_p95_ms": 50,
        "latency_target_met": p95 <= 50,
        "pipeline_p50_ms": float(np.quantile(pipeline, 0.5)),
        "pipeline_p95_ms": float(np.quantile(pipeline, 0.95)),
        "before": vars(before),
        "after": vars(guard.sample()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    del ort
    gc.collect()
    guard.close()
    print(json.dumps(receipt))
    # Missed engineering latency target is an explicit failed gate, not a pass.
    return 0 if receipt["latency_target_met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
