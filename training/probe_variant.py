"""Parity vs FP32 plus 128-token and short-ticket latency for one candidate graph (4 threads)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from training.parity_probe import TEXTS  # noqa: E402
from training.quant_sweep import FP32, compare  # noqa: E402
from training.release_bundle import feed, session, tokenizer_for  # noqa: E402


def timed(s, f, n=40):  # type: ignore[no-untyped-def]
    for _ in range(5):
        s.run(None, f)
    t = []
    for _ in range(n):
        a = time.perf_counter()
        s.run(None, f)
        t.append((time.perf_counter() - a) * 1000)
    return round(float(np.percentile(t, 50)), 1), round(float(np.percentile(t, 95)), 1)


def main() -> int:
    target = Path(sys.argv[1])
    tok = tokenizer_for(ROOT / "artifacts/release_candidate_bundle")
    feeds = [feed(tok, t) for t in TEXTS]
    ref = session(FP32, 4)
    expected = [ref.run(None, f) for f in feeds]
    del ref
    a = time.perf_counter()
    s = session(target, 4)
    load_ms = round((time.perf_counter() - a) * 1000)
    res = compare(expected, [s.run(None, f) for f in feeds])
    ids = tok.encode("VPN connection stopped working this morning for the whole department. " * 30).ids[:128]
    long = {
        "input_ids": np.asarray([ids], dtype=np.int64),
        "attention_mask": np.ones((1, 128), dtype=np.int64),
    }
    res["load_ms"] = load_ms
    res["p50_p95_128"] = timed(s, long)
    res["p50_p95_short"] = timed(s, feed(tok, "VPN is down this morning for the whole department, urgent."))
    print(json.dumps({target.name: res}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
