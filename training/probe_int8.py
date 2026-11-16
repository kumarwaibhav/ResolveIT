"""Quick INT8 probe: load time, 128-token latency, and pooled-feature distance of free text."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"

import numpy as np  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

from training.data import load  # noqa: E402
from training.inference import inputs, session  # noqa: E402

bundle = ROOT / "artifacts/release_candidate_bundle"
tok = AutoTokenizer.from_pretrained(ROOT / "artifacts/training/checkpoint/tokenizer", local_files_only=True)
out = {"cpu_count": os.cpu_count()}
for threads in (2, 4):
    t = time.perf_counter()
    s = session(bundle / "model_int8.onnx", threads=threads)
    load_s = time.perf_counter() - t
    text = "VPN is down for the whole floor since this morning " * 12
    feed = tok([text], truncation=True, max_length=128, padding="max_length", return_tensors="np")
    feed = {k: np.asarray(feed[k], dtype=np.int64) for k in ("input_ids", "attention_mask")}
    for _ in range(10):
        s.run(["pooled"], feed)
    lat = []
    for _ in range(60):
        t = time.perf_counter()
        s.run(["pooled"], feed)
        lat.append((time.perf_counter() - t) * 1000)
    out[f"threads_{threads}"] = {
        "load_s": round(load_s, 2),
        "p50_ms": round(float(np.percentile(lat, 50)), 2),
        "p95_ms": round(float(np.percentile(lat, 95)), 2),
        "tokens": 128,
    }
    if threads == 4:
        rows = [r for r in load(ROOT / "artifacts/training/multilingual.jsonl") if r["split"] == "train"][:60]
        tmpl = np.stack([s.run(["pooled"], inputs(tok, [r["text"]]))[0][0] for r in rows])
        free = [
            "VPN is down for the whole floor since this morning, urgent",
            "mera laptop bahut slow hai aur VPN bhi nahi chal raha",
            "Outlook keeps crashing when I open attachments",
            "I clicked a link in a suspicious email and my account got hacked",
        ]
        fv = np.stack([s.run(["pooled"], inputs(tok, [t]))[0][0] for t in free])
        mu, sd = tmpl.mean(0), np.maximum(tmpl.std(0), 0.1)
        z_t = np.abs((tmpl - mu) / sd).mean(1)
        z_f = np.abs((fv - mu) / sd).mean(1)
        out["mean_abs_z_template"] = round(float(z_t.mean()), 2)
        out["mean_abs_z_free_text"] = [round(float(v), 2) for v in z_f]
    del s
print(json.dumps(out, indent=1))
