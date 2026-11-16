"""Build the release-candidate bundle from the trained, quantized encoder.

Every number fitted here comes from the shipped INT8 ONNX model run exactly as the
API runs it (raw text -> NFKC -> PII mask -> tokenizers -> batch of one). The
encoder is not retrained. Fitted on its outputs: the external team head,
temperature, class-conditional conformal thresholds, per-queue routing
certificates before and after one truthful clarifying answer, and the theta
answer table. All rows are generated (label_source synthetic_seed); the result
certifies the generator, never customer traffic, and production_authorized
stays false.
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import onnxruntime as ort
from gpu_guard import ResourceGuard
from resolveit_core.bench.baselines import (
    TfidfLogistic,
    forced_single_label,
    metrics,
    naive_confidence,
    paired_bootstrap_accuracy,
)
from resolveit_core.calibrate.conformal_selective import (
    fit_conformal,
    fit_temperature,
    select_queue_taus,
    softmax,
)
from resolveit_core.frame.merger import frame_from_rules
from resolveit_core.gate.bayes_evsi import (
    ChannelCosts,
    CostMatrix,
    GateInput,
    ThetaTable,
    decide,
    finalize_after_answer,
    posterior_after_answer,
)
from resolveit_core.masking.pii_shield import mask_pii
from resolveit_core.model.features import (
    FEATURE_VERSION,
    FRAME_VOCAB,
    feature_row,
    fold_standardised_head,
    head_values,
)
from resolveit_core.offsets.offset_map import normalize_nfkc
from resolveit_core.rules.engine import run_rules
from resolveit_core.schemas import ASKABLE_STATES, TEAMS, UNKNOWN_ANSWER, Action, Slot
from tokenizers import Tokenizer
from verify_bundle import file_digest, verify_bundle

from training.data import load as load_seed
from training.data_free import GENERATOR
from training.data_free import write as write_free
from training.inference import representatives

FIXED_TIME = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
MAX_TOKENS = 192
SEED = 20261116
TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "spm.model",
)
GATE_SLOTS = tuple(FRAME_VOCAB)  # only slots whose answers name a value the head knows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def prepared(text: str) -> str:
    normalised, _ = normalize_nfkc(text)
    return mask_pii(normalised).masked_text


def tokenizer_for(bundle: Path) -> Tokenizer:
    tok = Tokenizer.from_file(str(bundle / "tokenizer" / "tokenizer.json"))
    tok.enable_truncation(max_length=MAX_TOKENS)
    tok.no_padding()
    return tok


def session(path: Path, threads: int) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = False
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def feed(tok: Tokenizer, text: str) -> dict[str, np.ndarray]:
    ids = tok.encode(prepared(text)).ids
    return {
        "input_ids": np.asarray([ids], dtype=np.int64),
        "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
    }


def label(row: dict[str, Any]) -> int:
    return [t.value for t in TEAMS].index(row["team"])


def assemble(
    seed_rows: list[dict[str, Any]], free_rows: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    seed_map = {
        "train": "head_train",
        "scaling": "scaling",
        "calibration": "calibration",
        "policy_selection": "policy_selection",
        "risk_certification": "risk_certification",
        "frozen_test": "frozen_test",
    }
    splits: dict[str, list[dict[str, Any]]] = {
        name: [] for name in (*seed_map.values(), "answer_certification")
    }
    for seed_split, target in seed_map.items():
        chosen = (
            [r for r in seed_rows if r["split"] == seed_split]
            if seed_split == "train"
            else representatives(seed_rows, seed_split)
        )
        splits[target] += [{**r, "kind": "seed_template", "service_key": UNKNOWN_ANSWER} for r in chosen]
    for row in free_rows:
        splits[row["split"]].append(row)
    return splits


def check_tokenizer(tok: Tokenizer, bundle: Path, rows: list[dict[str, Any]]) -> int:
    """The serving tokenizer must give exactly the ids the LoRA training tokenizer gave."""
    from transformers import AutoTokenizer

    hf = AutoTokenizer.from_pretrained(bundle / "tokenizer", local_files_only=True)
    for row in rows:
        text = prepared(row["text"])
        expected = hf(text, truncation=True, max_length=MAX_TOKENS)["input_ids"]
        if tok.encode(text).ids != expected:
            raise RuntimeError("tokenizers and transformers disagree; serving would drift from training")
    return len(rows)


def fit_head(x: np.ndarray, y: np.ndarray, l2: float, epochs: int = 600) -> dict[str, np.ndarray]:
    mean, scale = x.mean(0), np.maximum(x.std(0), 0.1)
    z = (x - mean) / scale
    w, b = np.zeros((z.shape[1], len(TEAMS))), np.zeros(len(TEAMS))
    for _ in range(epochs):
        p = softmax(z @ w + b)
        p[np.arange(len(y)), y] -= 1
        g = p / len(y)
        w -= 0.1 * (z.T @ g + l2 * w)
        b -= 0.1 * g.sum(0)
    return {"weights": w, "bias": b, "mean": mean, "scale": scale}


def certify(probs: np.ndarray, y: np.ndarray, conformal: Any, costs: CostMatrix) -> dict[int, Any]:
    expected = probs @ costs.delay
    decision = np.argmin(expected, axis=1)
    member = conformal.predict_sets(probs)
    eligible = member[np.arange(len(probs)), decision] & (member.sum(1) <= 3)
    eligible &= expected[np.arange(len(probs)), decision] <= costs.c_def
    return select_queue_taus(
        probs.max(1)[eligible], (decision != y)[eligible], decision[eligible], n_queues=len(TEAMS)
    )


def taus(certs: dict[int, Any]) -> dict[int, float | None]:
    return {q: c.tau_hat for q, c in certs.items()}


def simulate_gate(
    rows: list[dict[str, Any]],
    probs: np.ndarray,
    frames: list[Any],
    conformal: Any,
    costs: CostMatrix,
    theta: ThetaTable,
    before: dict[int, float | None],
    after: dict[int, float | None],
) -> dict[str, Any]:
    """Run the real gate on the frozen test split; ASK rows get the row's truthful answer."""
    out: dict[str, int] = {
        "route": 0,
        "route_correct": 0,
        "ask": 0,
        "ask_then_route": 0,
        "ask_then_route_correct": 0,
        "defer": 0,
        "empty_set": 0,
        "covered": 0,
    }
    for row, p, frame in zip(rows, probs, frames, strict=True):
        y = label(row)
        cset = conformal.predict_set(p)
        out["covered"] += y in cset
        out["empty_set"] += not cset
        askable = tuple(s.slot for s in frame.slots if s.state in ASKABLE_STATES and s.slot in theta.values)
        gate = GateInput(
            probs=p,
            conformal=conformal,
            costs=costs,
            theta=theta,
            channel=ChannelCosts(c_ask=1.0, c_ghost=10.0),
            askable_slots=askable,
            contradicted_critical=frozenset(),
            tau_hat=None,
            queue_tau_hat=before,
            answer_queue_tau_hat=after,
            critical_missing_slots=frozenset(s for s in askable if s is Slot.SERVICE),
        )
        result = decide(gate)
        if result.action is Action.ROUTE:
            out["route"] += 1
            out["route_correct"] += result.team == y
        elif result.action is Action.ASK:
            out["ask"] += 1
            answer = row["service_key"] if result.ask_slot is Slot.SERVICE else UNKNOWN_ANSWER
            final = finalize_after_answer(gate, result.ask_slot, answer)
            if final.action is Action.ROUTE:
                out["ask_then_route"] += 1
                out["ask_then_route_correct"] += final.team == y
        else:
            out["defer"] += 1
    n = len(rows)
    routed = out["route"] + out["ask_then_route"]
    correct = out["route_correct"] + out["ask_then_route_correct"]
    return {
        **out,
        "n": n,
        "conformal_marginal_coverage": out["covered"] / n,
        "auto_route_rate": routed / n,
        "misroute_rate_among_routed": None if routed == 0 else 1 - correct / routed,
    }


def latency(sess: ort.InferenceSession, tok: Tokenizer, texts: list[str]) -> dict[str, Any]:
    long = "VPN connection stopped working this morning for the whole department. " * 30
    ids = tok.encode(prepared(long)).ids[:128]
    full = {
        "input_ids": np.asarray([ids], dtype=np.int64),
        "attention_mask": np.ones((1, 128), dtype=np.int64),
    }
    report: dict[str, Any] = {}
    for name, feeds in (("tokens_128", [full] * 80), ("typical_tickets", [feed(tok, t) for t in texts])):
        for f in feeds[:10]:
            sess.run(["pooled"], f)
        samples = []
        for f in feeds:
            start = time.perf_counter()
            sess.run(["pooled"], f)
            samples.append((time.perf_counter() - start) * 1000)
        report[name] = {
            "n": len(samples),
            "p50_ms": round(float(np.percentile(samples, 50)), 2),
            "p95_ms": round(float(np.percentile(samples, 95)), 2),
        }
    report["typical_tokens_mean"] = round(
        float(np.mean([len(tok.encode(prepared(t)).ids) for t in texts])), 1
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/release_candidate_bundle")
    parser.add_argument("--fp32", type=Path, default=ROOT / "artifacts/training/fp32_export/model_fp32.onnx")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "artifacts/training/checkpoint")
    parser.add_argument("--threads", type=int, default=8)
    # 1e-4 left the head sensitive enough that INT8 rounding (pooled rmse 0.03) moved one
    # borderline probability by 0.116 > the predeclared 0.10. Stronger L2 = smoother head.
    parser.add_argument("--l2", type=float, default=5e-2)
    args = parser.parse_args()
    guard = ResourceGuard()
    before = guard.checkpoint()
    begin = time.perf_counter()
    bundle: Path = args.bundle
    for name in TOKENIZER_FILES:
        (bundle / "tokenizer").mkdir(exist_ok=True)
        shutil.copyfile(args.checkpoint / "tokenizer" / name, bundle / "tokenizer" / name)
    training_report = json.loads((args.checkpoint / "training_report.json").read_text(encoding="utf-8"))
    if training_report.get("pretrained_model_trained") is not True:
        raise ValueError("actual pretrained training receipt required")

    seed_rows = load_seed(ROOT / "artifacts/training/multilingual.jsonl")
    free_path = ROOT / "artifacts/training/freetext.jsonl"
    free_audit = write_free(free_path, SEED)
    free_rows = [json.loads(line) for line in free_path.read_text(encoding="utf-8").splitlines()]
    splits = assemble(seed_rows, free_rows)
    tok = tokenizer_for(bundle)
    checked = check_tokenizer(tok, bundle, splits["head_train"][::7] + splits["frozen_test"][::11])
    print(json.dumps({"phase": "tokenizer_parity", "rows": checked}), flush=True)

    sess = session(bundle / "model_int8.onnx", args.threads)
    # Pooled vectors depend only on (shipped model bytes, text): cache them so head/calibration
    # experiments do not re-run 12k INT8 inferences. A different model file is a different key.
    model_digest = file_digest(bundle / "model_int8.onnx")
    cache_dir = ROOT / "artifacts/training/pooled_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pooled: dict[str, np.ndarray] = {}
    frames: dict[str, list[Any]] = {}
    security: dict[str, np.ndarray] = {}
    for name, rows in splits.items():
        key = hashlib.sha256((model_digest + "\0" + "\0".join(r["text"] for r in rows)).encode()).hexdigest()
        cached = cache_dir / f"{key}.npy"
        hit = np.load(cached) if cached.exists() else None
        vectors, fr, sec = [], [], []
        for i, row in enumerate(rows):
            if i % 50 == 0:
                guard.checkpoint()
            if hit is None:
                vectors.append(sess.run(["pooled"], feed(tok, row["text"]))[0][0])
            rules = run_rules(row["text"], FIXED_TIME, "Asia/Kolkata")
            fr.append(frame_from_rules(rules))
            sec.append(rules.security_trigger)
        pooled[name] = hit if hit is not None else np.stack(vectors)
        if hit is None:
            np.save(cached, pooled[name])
        frames[name], security[name] = fr, np.array(sec)
        print(json.dumps({"phase": "int8_inference", "split": name, "n": len(rows)}), flush=True)

    def x_of(name: str) -> np.ndarray:
        return np.stack(
            [
                feature_row(p.astype(np.float64), bool(s), head_values(f))
                for p, s, f in zip(pooled[name], security[name], frames[name], strict=True)
            ]
        )

    xs = {name: x_of(name) for name in splits}
    ys = {name: np.array([label(r) for r in rows], dtype=np.int64) for name, rows in splits.items()}
    fitted = fit_head(xs["head_train"], ys["head_train"], args.l2)
    head = fold_standardised_head(fitted["weights"], fitted["bias"], fitted["mean"], fitted["scale"])
    logits = {name: x @ head.weights.T + head.bias for name, x in xs.items()}
    probe = splits["frozen_test"][0]
    direct = head.logits(
        np.concatenate([pooled["frozen_test"][0].astype(np.float64), [float(security["frozen_test"][0])]]),
        head_values(frames["frozen_test"][0]),
    )
    if not np.allclose(direct, logits["frozen_test"][0], atol=1e-9):
        raise RuntimeError("folded head disagrees with feature matrix")
    _ = probe

    temperature = fit_temperature(logits["scaling"], ys["scaling"])
    probs = {name: softmax(v, temperature) for name, v in logits.items()}
    conformal = fit_conformal(probs["calibration"], ys["calibration"], alpha=0.10, min_class_n=150, seed=SEED)
    costs = CostMatrix.uniform(240.0, 45.0)
    before_certs = certify(probs["risk_certification"], ys["risk_certification"], conformal, costs)

    theta = ThetaTable({slot: FRAME_VOCAB[slot] for slot in GATE_SLOTS}, kappa=10)
    for row, frame in zip(splits["head_train"], frames["head_train"], strict=True):
        values = {s.slot: s.value for s in frame.slots if s.value is not None}
        for slot in GATE_SLOTS:
            value = values.get(slot, UNKNOWN_ANSWER)
            theta.add(slot, value if value in theta.values[slot] else UNKNOWN_ANSWER, label(row))

    answer_rows = splits["answer_certification"]
    posts = np.stack(
        [
            posterior_after_answer(p, theta, Slot.SERVICE, row["service_key"])[0]
            for p, row in zip(probs["answer_certification"], answer_rows, strict=True)
        ]
    )
    after_certs = certify(posts, ys["answer_certification"], conformal, costs)
    before_taus, after_taus = taus(before_certs), taus(after_certs)
    print(json.dumps({"phase": "certificates", "before": before_taus, "after": after_taus}), flush=True)

    gate = simulate_gate(
        splits["frozen_test"],
        probs["frozen_test"],
        frames["frozen_test"],
        conformal,
        costs,
        theta,
        before_taus,
        after_taus,
    )
    test_y = ys["frozen_test"]
    texts = [r["text"] for r in splits["frozen_test"]]
    lexical = TfidfLogistic(len(TEAMS), max_features=2000)
    lexical.fit([r["text"] for r in splits["head_train"]], ys["head_train"], epochs=150)
    lexical_pred = lexical.predict(texts)
    forced = forced_single_label(probs["frozen_test"])
    kinds = np.array([r["kind"] for r in splits["frozen_test"]])
    by_kind = {k: asdict(metrics(forced[kinds == k], test_y[kinds == k])) for k in sorted(set(kinds))}

    timing = latency(sess, tok, texts[:120])
    del sess
    guard.checkpoint()
    fp32 = session(args.fp32, 4)
    q8 = session(bundle / "model_int8.onnx", 4)
    parity_rows = splits["policy_selection"][:24]
    errors: dict[str, dict[str, float]] = {}
    exp = [fp32.run(None, feed(tok, r["text"])) for r in parity_rows]
    act = [q8.run(None, feed(tok, r["text"])) for r in parity_rows]
    for i, name in enumerate(("bio_logits", "segment_logits", "pooled")):
        diffs = np.concatenate([(a[i] - b[i]).ravel() for a, b in zip(exp, act, strict=True)])
        errors[name] = {"max_abs": float(np.abs(diffs).max()), "rmse": float(np.sqrt(np.mean(diffs**2)))}
    rows_pp = [
        (
            np.concatenate([e[2][0], [float(sec)]]),
            np.concatenate([a[2][0], [float(sec)]]),
            head_values(f),
        )
        for e, a, f, sec in zip(
            exp,
            act,
            frames["policy_selection"][: len(parity_rows)],
            security["policy_selection"][: len(parity_rows)],
            strict=True,
        )
    ]
    team_diff = max(
        float(np.abs(head.probs(e, v, temperature) - head.probs(a, v, temperature)).max())
        for e, a, v in rows_pp
    )
    del fp32, q8
    parity = {
        "samples": len(parity_rows),
        "errors": errors,
        "team_probability_max_abs": team_diff,
        "predeclared_max_abs_logit": 2.0,
        "predeclared_rmse": 0.25,
        "predeclared_max_probability_difference": 0.10,
    }
    parity["passed"] = (
        all(v["rmse"] <= 0.25 and v["max_abs"] <= 2.0 for v in errors.values()) and team_diff <= 0.10
    )

    np.savez(
        bundle / "linear_head.npz",
        weights=head.weights,
        bias=head.bias,
        pooled_dim=np.array(head.pooled_dim),
        temperature=np.array(temperature),
    )
    calibration = {
        "label_source": "synthetic_seed",
        "production_eligible": False,
        "production_authorized": False,
        "model_outputs_used": "shipped_int8_block32_weights_dequantized_at_load_fp32_compute",
        "feature_version": FEATURE_VERSION,
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
        "alpha": conformal.alpha,
        "q_hat_y": conformal.thresholds.tolist(),
        "class_conditional_supported": conformal.class_conditional.tolist(),
        "class_counts": conformal.class_counts.tolist(),
        "pooled_q_hat": conformal.pooled_threshold,
        "epsilon": 0.05,
        "delta": 0.05,
        "queue_tau_hat": {TEAMS[q].value: t for q, t in before_taus.items()},
        "answer_queue_tau_hat": {TEAMS[q].value: t for q, t in after_taus.items()},
        "queue_certificates": {TEAMS[q].value: asdict(c) for q, c in before_certs.items()},
        "answer_queue_certificates": {TEAMS[q].value: asdict(c) for q, c in after_certs.items()},
        "answer_certificate_assumption": "simulated truthful answer to the service question, synthetic rows",
        "threshold_selection": "predeclared_grid_exact_binomial_Bonferroni_over_queues",
        "theta_kappa": 10,
        "theta_values": {s.value: list(v) for s, v in theta.values.items()},
        "theta_counts": {s.value: c.tolist() for s, c in theta.counts.items()},
        "L": costs.delay.tolist(),
        "defer_minutes": costs.c_def,
        "frame_vocabulary": {s.value: list(v) for s, v in FRAME_VOCAB.items()},
        "real_tenants": "shadow_only",
    }
    write_json(bundle / "calibration.json", calibration)
    report = {
        "label_source": "synthetic_seed",
        "production_eligible": False,
        "production_authorized": False,
        "pretrained_model_trained": True,
        "base_model": training_report["base_model"],
        "revision": training_report["revision"],
        "encoder_retrained_here": False,
        "encoder_outputs": training_report["encoder_outputs"],
        "team_head_inside_onnx": False,
        "head_training_rows": len(splits["head_train"]),
        "head_l2": args.l2,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "datasets": {"seed": training_report["dataset"], "freetext": free_audit},
        "training": {
            k: training_report[k]
            for k in (
                "epochs",
                "weighted_loss_first",
                "weighted_loss_last",
                "elapsed_seconds",
                "versions",
                "precision",
            )
        },
        "parity": parity,
        "latency_ms": {"threads": args.threads, **timing},
        "human_frozen_test_metrics": None,
        "synthetic_frozen_test": {
            "forced_single_label": asdict(metrics(forced, test_y)),
            "forced_single_label_by_kind": by_kind,
            "naive_threshold_0.8": asdict(metrics(naive_confidence(probs["frozen_test"]), test_y)),
            "tfidf_logistic": asdict(metrics(lexical_pred, test_y)),
            "paired_bootstrap_forced_minus_tfidf": paired_bootstrap_accuracy(
                forced, lexical_pred, test_y, resamples=2000, seed=SEED
            ),
            "zero_shot_llm": None,
            "zero_shot_unavailable_reason": "no independent external predictions; LLMs stay out of decisions",
            "gate_simulation": gate,
            "caveat": "vague rows carry random labels by construction; template overlap with head data",
        },
        "before": vars(before),
        "after": vars(guard.sample()),
        "elapsed_seconds": round(time.perf_counter() - begin, 1),
    }
    write_json(bundle / "report.json", report)
    write_json(bundle / "dataset_audit.json", {"seed": training_report["dataset"], "freetext": free_audit})
    files = {
        p.relative_to(bundle).as_posix(): file_digest(p)
        for p in sorted(bundle.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    bundle_id = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    write_json(
        bundle / "manifest.json",
        {
            "bundle_id": bundle_id,
            "files": files,
            "label_source": "synthetic_seed",
            "production_eligible": False,
            "production_authorized": False,
            "generator": [GENERATOR, "resolveit-template-v1"],
        },
    )
    print(json.dumps({"phase": "verify", **verify_bundle(bundle, bundle_id)}), flush=True)
    print(
        json.dumps(
            {
                "phase": "done",
                "bundle_id": bundle_id,
                "parity_passed": parity["passed"],
                "latency": timing,
                "gate": gate,
            }
        ),
        flush=True,
    )
    guard.close()
    return 0 if parity["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
