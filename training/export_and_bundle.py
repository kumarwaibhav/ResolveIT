"""Export real merged encoder, quantize, then fit only shipped INT8 outputs.

This small generated seed yields low-support human-gated certificates. Statistical
claims cannot be transferred from generator data to customer incidents.
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("HF_HOME", str(ROOT / "artifacts/cache/huggingface"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
from gpu_guard import ResourceGuard
from resolveit_core.bench.baselines import (
    TfidfLogistic,
    forced_single_label,
    metrics,
    naive_confidence,
    paired_bootstrap_accuracy,
    zero_shot_cached,
)
from resolveit_core.calibrate.conformal_selective import (
    fit_conformal,
    fit_temperature,
    select_queue_taus,
    softmax,
)
from resolveit_core.gate.bayes_evsi import CostMatrix, ThetaTable
from resolveit_core.schemas import SLOTS, TEAMS, UNKNOWN_ANSWER
from verify_bundle import file_digest, verify_bundle

from training.data import audit_rows, load, sample_weight
from training.inference import (
    FRAME_VOCAB,
    features,
    frame_encoder,
    frame_values,
    head_logits,
    inputs,
    labels,
    representatives,
    session,
)


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def export(checkpoint: Path, output: Path, guard: ResourceGuard) -> None:
    for phase in ("export", "quantize"):
        guard.checkpoint()
        env = dict(os.environ)
        if phase == "export":
            env["USE_TORCH"] = "1"
        else:
            env.update(USE_TORCH="0", USE_TF="0")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "training/graph_phase.py"),
                phase,
                "--checkpoint",
                str(checkpoint),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
    shutil.copytree(checkpoint / "tokenizer", output / "tokenizer", dirs_exist_ok=True)


def extract(ort: Any, tokenizer: Any, rows: list[dict[str, Any]], guard: ResourceGuard) -> np.ndarray:
    pooled = []
    for row in rows:
        guard.checkpoint()
        pooled.append(ort.run(["pooled"], inputs(tokenizer, [row["text"]]))[0][0])
    return features(np.stack(pooled), [row["text"] for row in rows])


def fit_head(x: np.ndarray, y: np.ndarray, weights: np.ndarray, guard: ResourceGuard) -> dict[str, Any]:
    mean, scale = x.mean(0), x.std(0)
    scale = np.maximum(scale, 0.1)
    x = (x - mean) / scale
    matrix, bias = np.zeros((x.shape[1], len(TEAMS))), np.zeros(len(TEAMS))
    for epoch in range(300):
        if epoch % 25 == 0:
            guard.checkpoint()
        probabilities = softmax(x @ matrix + bias)
        probabilities[np.arange(len(y)), y] -= 1
        gradient = probabilities * weights[:, None] / len(y)
        matrix -= 0.1 * (x.T @ gradient + 1e-4 * matrix)
        bias -= 0.1 * gradient.sum(0)
    return {"weights": matrix, "bias": bias, "mean": mean, "scale": scale}


def parity(
    output: Path, tokenizer: Any, rows: list[dict[str, Any]], guard: ResourceGuard, head: Any | None = None
) -> dict[str, Any]:
    # Load only one large ORT session at a time to preserve Windows headroom.
    feed = [inputs(tokenizer, [row["text"]]) for row in rows]
    guard.checkpoint()
    full = session(output / "model_fp32.onnx")
    expected = [full.run(None, item) for item in feed]
    del full
    gc.collect()
    guard.checkpoint()
    quantized = session(output / "model_int8.onnx")
    actual = [quantized.run(None, item) for item in feed]
    del quantized
    gc.collect()
    errors = {}
    for index, name in enumerate(("bio_logits", "segment_logits", "pooled")):
        absolute = max(
            float(np.max(np.abs(a[index] - b[index]))) for a, b in zip(expected, actual, strict=True)
        )
        rms = float(
            np.sqrt(
                np.mean(
                    np.concatenate(
                        [(a[index] - b[index]).ravel() ** 2 for a, b in zip(expected, actual, strict=True)]
                    )
                )
            )
        )
        errors[name] = {"max_abs": absolute, "rmse": rms}
    # Fixed, predeclared mechanical export gate; not a task-quality certificate.
    if any(value["rmse"] > 0.25 or value["max_abs"] > 2 for value in errors.values()):
        raise RuntimeError(f"Predeclared encoder parity gate failed: {errors}")
    if head is not None:
        texts = [row["text"] for row in rows]
        fp = softmax(head_logits(features(np.concatenate([item[2] for item in expected]), texts), head))
        qp = softmax(head_logits(features(np.concatenate([item[2] for item in actual]), texts), head))
        errors["team_probability"] = {"max_abs": float(np.max(np.abs(fp - qp)))}
        if errors["team_probability"]["max_abs"] > 0.10:
            raise RuntimeError("Predeclared external-head probability parity gate failed")
    return {
        "passed": True,
        "samples": len(rows),
        "errors": errors,
        "predeclared_max_abs_logit": 2,
        "predeclared_rmse": 0.25,
        "predeclared_max_probability_difference": 0.10,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "artifacts/training/checkpoint")
    parser.add_argument("--data", type=Path, default=ROOT / "artifacts/training/multilingual.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/release_candidate_bundle")
    parser.add_argument("--reuse-export", action="store_true")
    args = parser.parse_args()
    guard = ResourceGuard()
    before = guard.checkpoint()
    begin = time.perf_counter()
    rows = load(args.data)
    if {row["label_source"] for row in rows} != {"synthetic_seed"}:
        raise ValueError(
            "This seed-release pipeline requires synthetic_seed rows; other provenance needs its own report"
        )
    training_report = json.loads((args.checkpoint / "training_report.json").read_text())
    if training_report.get("pretrained_model_trained") is not True:
        raise ValueError("Actual pretrained training receipt is required")
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.reuse_export:
        export(args.checkpoint, args.output, guard)
    elif not (args.output / "model_int8.onnx").exists():
        raise ValueError("Reuse requires existing exported graph")
    else:
        shutil.copytree(args.checkpoint / "tokenizer", args.output / "tokenizer", dirs_exist_ok=True)
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.output / "tokenizer", local_files_only=True)
    splits = {
        split: representatives(rows, split)
        for split in (
            "train",
            "scaling",
            "calibration",
            "policy_selection",
            "risk_certification",
            "frozen_test",
        )
    }
    # All three training translations may inform the head. Every certificate /
    # test observation remains one predeclared independently generated group.
    splits["train"] = [row for row in rows if row["split"] == "train"]
    quantized = session(args.output / "model_int8.onnx")
    extracted = {}
    for name, subset in splits.items():
        extracted[name] = extract(quantized, tokenizer, subset, guard)
        print(json.dumps({"phase": "int8_inference", "split": name, "n": len(subset)}), flush=True)
    head = fit_head(
        extracted["train"],
        labels(splits["train"]),
        np.array([sample_weight(row) for row in splits["train"]]),
        guard,
    )
    np.savez(args.output / "linear_head.npz", **head)
    logits = {name: head_logits(x, head) for name, x in extracted.items()}
    temperature = fit_temperature(logits["scaling"], labels(splits["scaling"]))
    conformal = fit_conformal(
        softmax(logits["calibration"], temperature),
        labels(splits["calibration"]),
        alpha=0.10,
        min_class_n=150,
        seed=20261115,
    )
    costs = CostMatrix.uniform(240, 45)
    # Costs/eligibility and the finite grid are fixed before certification.
    # Policy-selection is a disjoint diagnostic draw, never an extra risk draw.
    risk = softmax(logits["risk_certification"], temperature)
    decisions = np.argmin(risk @ costs.delay, axis=1)
    memberships = conformal.predict_sets(risk)
    eligible = memberships[np.arange(len(risk)), decisions] & (memberships.sum(1) <= 3)
    eligible &= (risk @ costs.delay)[np.arange(len(risk)), decisions] <= costs.c_def
    certificates = select_queue_taus(
        risk.max(1)[eligible],
        (decisions != labels(splits["risk_certification"]))[eligible],
        decisions[eligible],
        n_queues=len(TEAMS),
    )
    theta = ThetaTable({slot: FRAME_VOCAB.get(slot.value, ("stated",)) for slot in SLOTS}, kappa=10)
    # One response observation/group; all are synthetic, not real ask histories.
    for row in representatives(rows, "train"):
        values = frame_values(row["text"])
        for slot in SLOTS:
            theta.add(
                slot, values.get(slot, UNKNOWN_ANSWER), int(labels([row])[0]), weight=sample_weight(row)
            )
    calibration = {
        "label_source": "synthetic_seed",
        "production_eligible": False,
        "production_authorized": False,
        "model_outputs_used": "shipped_matmul_int8_onnx",
        "temperature": temperature,
        "alpha": conformal.alpha,
        "q_hat_y": conformal.thresholds.tolist(),
        "class_conditional_supported": conformal.class_conditional.tolist(),
        "class_counts": conformal.class_counts.tolist(),
        "pooled_q_hat": conformal.pooled_threshold,
        "epsilon": 0.05,
        "delta": 0.05,
        "queue_certificates": {TEAMS[q].value: asdict(value) for q, value in certificates.items()},
        "threshold_selection": "predeclared_grid_exact_Bonferroni_over_queues_and_grid",
        "post_answer_certificates": None,
        "independent_unit": "one_sha256_selected_locale_per_group",
        "split_counts": {name: len(subset) for name, subset in splits.items()},
        "theta_kappa": 10,
        "theta_values": {s.value: v for s, v in theta.values.items()},
        "theta_counts": {s.value: value.tolist() for s, value in theta.counts.items()},
        "L": costs.delay.tolist(),
        "defer_minutes": costs.c_def,
        "channel_prior": {"alpha": 4, "beta": 2, "rho_0": 4 / 6},
        "exploration_floor": 0.05,
        "no_ask_holdout": 0.10,
        "frame_vocabulary": {s.value: v for s, v in frame_encoder().vocab.items()},
        "frame_features": "raw_first_rules_never_gold_spans",
        "real_tenants": "shadow_only",
    }
    write(args.output / "calibration.json", calibration)
    test_y = labels(splits["frozen_test"])
    probabilities = softmax(logits["frozen_test"], temperature)
    forced = forced_single_label(probabilities)
    naive = naive_confidence(probabilities)
    texts = [row["text"] for row in splits["frozen_test"]]
    baseline = TfidfLogistic(len(TEAMS), max_features=1000)
    guard.checkpoint()
    baseline.fit([row["text"] for row in splits["train"]], labels(splits["train"]), epochs=100)
    lexical = baseline.predict(texts)
    zero, family_bias = zero_shot_cached(
        None, test_y, model_family="unavailable", silver_annotator_family=None
    )
    del quantized
    gc.collect()
    parity_report = parity(args.output, tokenizer, splits["policy_selection"][:6], guard, head)
    report = {
        "label_source": "synthetic_seed",
        "production_eligible": False,
        "production_authorized": False,
        "pretrained_model_trained": True,
        "base_model": training_report["base_model"],
        "revision": training_report["revision"],
        "encoder_outputs": training_report["encoder_outputs"],
        "team_head_inside_onnx": False,
        "dataset": audit_rows(rows),
        "training": training_report,
        "parity": parity_report,
        "human_frozen_test_metrics": None,
        "synthetic_metrics": {
            "forced_single_label": asdict(metrics(forced, test_y)),
            "naive_threshold": asdict(metrics(naive, test_y)),
            "tfidf_logistic": asdict(metrics(lexical, test_y)),
            "zero_shot": zero,
            "zero_shot_unavailable_reason": "No independent external predictions supplied",
            "silver_family_bias": family_bias,
            "template_family_overlap_bias": True,
            "paired_bootstrap_forced_minus_tfidf": paired_bootstrap_accuracy(
                forced, lexical, test_y, resamples=2000, seed=20261115
            ),
            "bootstrap_unit": "incident_group",
            "bootstrap_resamples": 2000,
        },
        "before": vars(before),
        "after": vars(guard.sample()),
        "elapsed_seconds": time.perf_counter() - begin,
    }
    write(args.output / "report.json", report)
    shutil.copyfile(args.data.with_suffix(".audit.json"), args.output / "dataset_audit.json")
    files = {
        path.relative_to(args.output).as_posix(): file_digest(path)
        for path in args.output.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    bundle_id = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    write(
        args.output / "manifest.json",
        {
            "bundle_id": bundle_id,
            "files": files,
            "label_source": "synthetic_seed",
            "production_eligible": False,
            "production_authorized": False,
        },
    )
    verification = verify_bundle(args.output, bundle_id)
    print(json.dumps(verification))
    guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
