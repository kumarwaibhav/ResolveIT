"""Find an INT8 graph that keeps FP32 parity: sweep which weight MatMuls get dynamic INT8.

Dynamic quantization also quantizes each MatMul's *input activation* per tensor at run time.
DeBERTa-v3 has a few huge outlier activation channels, so a per-tensor scale wipes out the
rest of the vector. The sweep measures parity and latency per variant on fixed tickets.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import onnx  # noqa: E402
from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: E402

from training.parity_probe import TEXTS  # noqa: E402
from training.release_bundle import feed, session, tokenizer_for  # noqa: E402

FP32 = ROOT / "artifacts/training/fp32_export/model_fp32.onnx"
OUT = ROOT / "artifacts/training/sweep"


def weight_matmuls() -> list[str]:
    m = onnx.load(str(FP32), load_external_data=False)
    w = {t.name for t in m.graph.initializer}
    return [n.name for n in m.graph.node if n.op_type == "MatMul" and n.input[1] in w]


def all_matmuls() -> list[str]:
    m = onnx.load(str(FP32), load_external_data=False)
    return [n.name for n in m.graph.node if n.op_type == "MatMul"]


def compare(expected: list, actual: list) -> dict:
    out = {}
    for i, name in enumerate(("bio_logits", "segment_logits", "pooled")):
        d = np.concatenate([(a[i] - b[i]).ravel() for a, b in zip(expected, actual, strict=True)])
        out[name] = {
            "max_abs": round(float(np.abs(d).max()), 4),
            "rmse": round(float(np.sqrt((d**2).mean())), 4),
        }
    cos = [
        float(np.dot(a[2][0], b[2][0]) / (np.linalg.norm(a[2][0]) * np.linalg.norm(b[2][0])))
        for a, b in zip(expected, actual, strict=True)
    ]
    out["pooled_cosine_min"] = round(min(cos), 4)
    out["passes"] = all(v["max_abs"] <= 2 and v["rmse"] <= 0.25 for v in out.values() if isinstance(v, dict))
    return out


def timing(path: Path, tok, threads: int = 4) -> dict:
    s = session(path, threads)
    f = feed(tok, " ".join(["printer queue stuck on floor three since monday"] * 30))
    for _ in range(3):
        s.run(None, f)
    t = []
    for _ in range(25):
        a = time.perf_counter()
        s.run(None, f)
        t.append((time.perf_counter() - a) * 1000)
    return {
        "tokens": int(f["input_ids"].shape[1]),
        "p50_ms": round(float(np.percentile(t, 50)), 1),
        "p95_ms": round(float(np.percentile(t, 95)), 1),
    }


def variants(names: list[str]) -> dict[str, list[str]]:
    def keep(*parts: str) -> list[str]:
        return [n for n in names if any(p in n for p in parts)]

    return {
        "attn_qkvo": keep("query_proj", "key_proj", "value_proj", "attention/output/dense"),
        "attn_plus_ffn_up": keep(
            "query_proj", "key_proj", "value_proj", "attention/output/dense", "intermediate/dense"
        ),
        "all_but_ffn_down": [n for n in names if "/output/dense" not in n or "attention" in n],
        "qkv_only": keep("query_proj", "key_proj", "value_proj"),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tok = tokenizer_for(ROOT / "artifacts/release_candidate_bundle")
    feeds = [feed(tok, t) for t in TEXTS]
    ref = session(FP32, 4)
    expected = [ref.run(None, f) for f in feeds]
    del ref
    report: dict = {"fp32": timing(FP32, tok)}
    print(json.dumps({"fp32": report["fp32"]}), flush=True)
    names = weight_matmuls()
    every = all_matmuls()
    only = [v for v in sys.argv[1:]]
    for name, chosen in variants(names).items():
        if only and name not in only:
            continue
        target = OUT / f"{name}.onnx"
        quantize_dynamic(
            str(FP32),
            str(target),
            weight_type=QuantType.QInt8,
            per_channel=True,
            op_types_to_quantize=["MatMul"],
            nodes_to_exclude=[n for n in every if n not in chosen],
        )
        q = session(target, 4)
        res = {"quantized": len(chosen), **compare(expected, [q.run(None, f) for f in feeds])}
        del q
        res["latency"] = timing(target, tok)
        res["mb"] = round(target.stat().st_size / 2**20)
        report[name] = res
        print(json.dumps({name: res}), flush=True)
    (OUT / "sweep.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
