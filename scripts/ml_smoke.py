"""Export and verify an INT8 three-head SYNTHETIC FIXTURE, never a trained text model.

Usage: .venv/Scripts/python scripts/ml_smoke.py --output artifacts/ml-smoke
Requires core, onnx, onnxruntime and psutil. Every substantial phase is guarded.
This checks artifact/calibration plumbing; it does not establish multilingual quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import onnx
import onnxruntime as ort
from gpu_guard import ResourceGuard
from onnx import TensorProto, helper, numpy_helper
from onnxruntime.quantization import QuantType, quantize_dynamic
from resolveit_core.calibrate.conformal_selective import (
    fit_conformal,
    fit_temperature,
    select_queue_taus,
    softmax,
)

DIM, TEAMS, SLOTS = 32, 12, 11


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def data(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
    labels = rng.integers(0, TEAMS, n, dtype=np.int64)
    features = rng.normal(0, 0.1, (n, DIM)).astype(np.float32)
    features[np.arange(n), labels] += 1
    return features, labels


def train(rng: np.random.Generator, guard: ResourceGuard) -> dict[str, np.ndarray]:
    x, y = data(rng, 480)
    weights = {
        "team": rng.normal(0, 0.01, (DIM, TEAMS)).astype(np.float32),
        "state": rng.normal(0, 0.01, (DIM, SLOTS * 4)).astype(np.float32),
        "boundary": rng.normal(0, 0.01, (DIM, SLOTS * 2)).astype(np.float32),
    }
    # Fixture auxiliary targets are deterministic synthetic geometry, not human spans.
    state = (y[:, None] + np.arange(SLOTS)) % 4
    boundary = np.stack([y / 24, y / 24 + 0.1], axis=1)
    boundary = np.tile(boundary, (1, SLOTS)).astype(np.float32)
    for _ in range(50):
        guard.checkpoint()
        p = softmax(x @ weights["team"]).astype(np.float32)
        p[np.arange(len(y)), y] -= 1
        weights["team"] -= 0.5 * x.T @ p / len(y)
        q = softmax((x @ weights["state"]).reshape(-1, SLOTS, 4)).astype(np.float32)
        q[np.arange(len(y))[:, None], np.arange(SLOTS), state] -= 1
        weights["state"] -= 0.5 * x.T @ q.reshape(len(y), -1) / len(y)
        weights["boundary"] -= 0.5 * x.T @ (x @ weights["boundary"] - boundary) / len(y)
    return weights


def export(weights: dict[str, np.ndarray], path: Path) -> None:
    nodes, initializers, outputs = [], [], []
    for name, w in weights.items():
        initializers.append(numpy_helper.from_array(w, name=f"{name}_weight"))
        nodes.append(helper.make_node("MatMul", ["features", f"{name}_weight"], [name]))
        outputs.append(helper.make_tensor_value_info(name, TensorProto.FLOAT, ["batch", w.shape[1]]))
    graph = helper.make_graph(nodes, "synthetic_fixture_three_head", [
        helper.make_tensor_value_info("features", TensorProto.FLOAT, ["batch", DIM])
    ], outputs, initializer=initializers)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
    onnx.checker.check_model(model)
    onnx.save(model, path)


def session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/ml-smoke"))
    args = parser.parse_args()
    guard = ResourceGuard()
    guard.checkpoint()  # fail before allocating/training when system RAM exceeds 80%
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261114)
    weights = train(rng, guard)
    fp32, int8 = args.output / "model_fp32.onnx", args.output / "model_int8.onnx"
    export(weights, fp32)
    guard.checkpoint()
    quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"])
    graph = onnx.load(int8)
    if not any(n.op_type == "MatMulInteger" for n in graph.graph.node):
        raise RuntimeError("INT8 graph contains no quantized MatMul")
    full, quantized = session(fp32), session(int8)
    parity_x, _ = data(rng, 48)
    before = full.run(None, {"features": parity_x})
    after = quantized.run(None, {"features": parity_x})
    errors = {name: float(np.max(np.abs(a - b))) for name, a, b in zip(weights, before, after, strict=True)}
    if max(errors.values()) > 0.15:
        raise RuntimeError(f"FP32/INT8 parity gate failed: {errors}")

    def infer(n: int) -> tuple[np.ndarray, np.ndarray]:
        guard.checkpoint()
        x, y = data(rng, n)
        return np.asarray(quantized.run(["team"], {"features": x})[0], dtype=np.float64), y

    # Four disjoint generated draws: temperature, conformal, certification, test.
    scaling_logits, scaling_y = infer(240)
    temperature = fit_temperature(scaling_logits, scaling_y)
    conformal_logits, conformal_y = infer(600)
    conformal = fit_conformal(softmax(conformal_logits, temperature), conformal_y, min_class_n=30)
    cert_logits, cert_y = infer(2400)
    p = softmax(cert_logits, temperature)
    predicted = p.argmax(axis=1)
    membership = conformal.predict_sets(p)
    eligible = membership[np.arange(len(p)), predicted] & (membership.sum(axis=1) <= 3)
    queue = select_queue_taus(p.max(axis=1)[eligible], (predicted != cert_y)[eligible],
                             predicted[eligible], n_queues=TEAMS)
    write_json(args.output / "calibration.json", {
        "label_source": "synthetic_seed", "production_eligible": False,
        "temperature": temperature, "thresholds": conformal.thresholds.tolist(),
        "queue_tau_hat": {str(k): v.tau_hat for k, v in queue.items()},
        "certification_population": "frozen pre-answer gate-eligible synthetic fixture",
        "post_answer_certified": False,
    })
    test_logits, test_y = infer(240)
    test_p = softmax(test_logits, temperature)
    write_json(args.output / "report.json", {
        "architecture": "synthetic_fixture_three_head_linear", "label_source": "synthetic_seed",
        "production_eligible": False, "human_frozen_test_metrics": None,
        "split_sizes": {"train": 480, "scaling": 240, "conformal": 600, "certification": 2400, "test": 240},
        "quantization": "dynamic MatMul signed INT8 weights; opset17", "max_abs_logit_error": errors,
        "synthetic_fixture_team_accuracy": float(np.mean(test_p.argmax(axis=1) == test_y)),
        "heads": ["team", "11-slot epistemic state", "11 synthetic span boundaries"],
        "pretrained_model_trained": False, "multilingual_quality_established": False,
    })
    files = [fp32, int8, args.output / "calibration.json", args.output / "report.json"]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    write_json(args.output / "manifest.json", {
        "files": hashes, "bundle_id": hashlib.sha256(canonical).hexdigest(),
        "production_eligible": False, "label_source": "synthetic_seed",
    })
    print(json.dumps({"output": str(args.output.resolve()), "parity": errors, "production_eligible": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
