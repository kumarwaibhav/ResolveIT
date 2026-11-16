"""Actual pinned mDeBERTa LoRA training; synthetic execution is not human quality."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("HF_HOME", str(ROOT / "artifacts/cache/huggingface"))
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_ENABLE_PARALLEL_LOADING", "false")

from gpu_guard import ResourceGuard, ResourceLimit  # noqa: E402
from resolveit_core.masking.pii_shield import mask_pii  # noqa: E402
from resolveit_core.offsets.offset_map import OffsetChain, normalize_nfkc  # noqa: E402
from resolveit_core.schemas import SLOTS  # noqa: E402

from training.data import audit_rows, generate, load, sample_weight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "artifacts/training/multilingual.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/training/checkpoint")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument(
        "--resume", action="store_true", help="Resume only the same pinned dataset/checkpoint"
    )
    args = parser.parse_args()
    executed_sources = {
        name: hashlib.sha256((ROOT / "training" / name).read_bytes()).hexdigest()
        for name in ("train_lora_6gb.py", "model.py", "data.py")
    }
    guard = ResourceGuard(require_gpu=True)
    initial = guard.checkpoint()
    if initial.gpu_temperature is None or initial.gpu_temperature >= 65:
        raise ResourceLimit("Training launch requires GPU below65C")
    if not args.data.exists():
        generate(args.data)
    rows = load(args.data)
    audit = audit_rows(rows)
    training = [row for row in rows if row["split"] == "train"]
    import numpy as np
    import torch
    from torch.nn import functional as functional

    from training.model import MODEL_ID, REVISION, create_training_model

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; no silent CPU replacement")
    torch.set_num_threads(2)
    torch.manual_seed(20261115)
    torch.cuda.manual_seed_all(20261115)
    free_vram, total_vram = torch.cuda.mem_get_info()
    reserve = 512 * 1024**2
    if free_vram <= reserve:
        raise ResourceLimit("Insufficient free VRAM for safety reserve")
    torch.cuda.set_per_process_memory_fraction((free_vram - reserve) / total_vram)
    model, tokenizer, original_vocab = create_training_model(args.output if args.resume else None)
    model.train()
    parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=2e-4)
    args.output.mkdir(parents=True, exist_ok=True)
    seen, steps, updates = 0, 0, 0
    losses: list[float] = []
    telemetry = [vars(initial)]
    begin = time.perf_counter()
    precision = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=precision == torch.float16)
    if args.resume:
        saved = torch.load(args.output / "optimizer.pt", map_location="cpu", weights_only=True)
        if saved.get("dataset_sha256") != audit["dataset_sha256"] or saved.get("base_revision") != REVISION:
            raise ValueError("Resume requires matching pinned model revision and dataset identity")
        optimizer.load_state_dict(saved["optimizer"])
        steps, updates, seen = saved["steps"], saved["updates"], saved["examples_seen"]
        for name, parameter in model.named_parameters():
            if name in saved.get("gradients", {}):
                parameter.grad = saved["gradients"][name].to(parameter.device, dtype=parameter.dtype)
        if "scaler" in saved:
            scaler.load_state_dict(saved["scaler"])
        torch.set_rng_state(saved["torch_rng_state"])
        torch.cuda.set_rng_state_all(saved["cuda_rng_states"])
        losses = saved.get("losses", [])

    def checkpoint() -> None:
        model.backbone.save_pretrained(args.output / "adapter", safe_serialization=True)
        tokenizer.save_pretrained(args.output / "tokenizer")
        torch.save(
            {"bio": model.bio.state_dict(), "boundary": model.boundary.state_dict()}, args.output / "heads.pt"
        )
        torch.save(
            {
                "optimizer": optimizer.state_dict(),
                "steps": steps,
                "updates": updates,
                "examples_seen": seen,
                "dataset_sha256": audit["dataset_sha256"],
                "base_revision": REVISION,
                "gradients": {
                    name: p.grad.detach().cpu() for name, p in model.named_parameters() if p.grad is not None
                },
                "scaler": scaler.state_dict(),
                "losses": losses,
                "torch_rng_state": torch.get_rng_state(),
                "cuda_rng_states": torch.cuda.get_rng_state_all(),
                "executed_sources": executed_sources,
            },
            args.output / "optimizer.pt",
        )

    def encode(batch: list[dict]) -> tuple[dict, object, object, object]:
        texts, spans, boundaries = [], [], []
        for row in batch:
            normalized, first = normalize_nfkc(row["text"])
            masked = mask_pii(normalized)
            chain = OffsetChain([first, masked.offset_map])
            texts.append(masked.masked_text)
            spans.append(
                {slot.value: [chain.from_raw(*span) for span in row["spans"][slot.value]] for slot in SLOTS}
            )
            boundaries.append([chain.from_raw(start, end)[0] for start, end in row["segments"]])
        tokenized = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=192,
            return_offsets_mapping=True,
            return_tensors="pt",
        )
        offsets = tokenized.pop("offset_mapping").tolist()
        bio = torch.full_like(tokenized["input_ids"], -100)
        segment = torch.full_like(bio, -100)
        for i, mapping in enumerate(offsets):
            for t, (start, end) in enumerate(mapping):
                if start == end:
                    continue
                bio[i, t], segment[i, t] = 0, 0
                matches = [
                    (j, a)
                    for j, slot in enumerate(SLOTS)
                    for a, b in spans[i][slot.value]
                    if a < end and start < b
                ]
                if len(matches) == 1:
                    j, a = matches[0]
                    bio[i, t] = 1 + j * 2 + int(start > a)
                elif len(matches) > 1:
                    bio[i, t] = -100
                if any(start <= a < end for a in boundaries[i]):
                    segment[i, t] = 1
        inputs = {
            key: value.cuda() for key, value in tokenized.items() if key in ("input_ids", "attention_mask")
        }
        return (
            inputs,
            bio.cuda(),
            segment.cuda(),
            torch.tensor([sample_weight(row) for row in batch], device="cuda"),
        )

    if not args.resume:
        optimizer.zero_grad(set_to_none=True)
    try:
        for epoch in range(args.epochs):
            order = np.random.default_rng(20261115 + epoch).permutation(len(training))
            batches = [order[i : i + 4] for i in range(0, len(order), 4)]
            for b, indices in enumerate(batches):
                if epoch * len(batches) + b < steps:
                    continue
                snap = guard.checkpoint(save=checkpoint)
                telemetry.append(vars(snap))
                inputs, bio_y, segment_y, weights = encode([training[int(i)] for i in indices])
                with torch.autocast("cuda", dtype=precision):
                    bio, segment, _ = model(**inputs)
                    bio_loss = functional.cross_entropy(bio.transpose(1, 2), bio_y, reduction="none")
                    seg_loss = functional.cross_entropy(segment.transpose(1, 2), segment_y, reduction="none")
                    valid = bio_y != -100
                    bio_loss = (bio_loss * valid).sum(1) / valid.sum(1).clamp_min(1)
                    valid_seg = segment_y != -100
                    seg_loss = (seg_loss * valid_seg).sum(1) / valid_seg.sum(1).clamp_min(1)
                    loss = ((bio_loss + seg_loss) * weights).mean()
                losses.append(float(loss.detach().cpu()))
                scaler.scale(loss / 8).backward()
                steps += 1
                seen += len(indices)
                if (b + 1) % 8 == 0 or b == len(batches) - 1:
                    scaler.unscale_(optimizer)
                    remainder = (b + 1) % 8
                    if b == len(batches) - 1 and remainder:
                        for parameter in parameters:
                            if parameter.grad is not None:
                                parameter.grad.mul_(8 / remainder)
                    torch.nn.utils.clip_grad_norm_(parameters, 1)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
                    updates += 1
                if steps % 8 == 0:
                    print(
                        json.dumps(
                            {
                                "epoch": epoch + 1,
                                "microbatches": steps,
                                "optimizer_updates": updates,
                                "loss": losses[-1],
                                "gpu_C": snap.gpu_temperature,
                            }
                        ),
                        flush=True,
                    )
            torch.cuda.empty_cache()
        checkpoint()
    except (ResourceLimit, KeyboardInterrupt):
        checkpoint()
        raise
    finally:
        torch.cuda.empty_cache()
    import importlib.metadata

    report = {
        "base_model": MODEL_ID,
        "source_files_sha256_at_launch": executed_sources,
        "source_files_unchanged_at_completion": all(
            hashlib.sha256((ROOT / "training" / name).read_bytes()).hexdigest() == digest
            for name, digest in executed_sources.items()
        ),
        "offline_pinned_cache_only": True,
        "safetensors_auto_conversion_disabled": True,
        "revision": REVISION,
        "pretrained_model_trained": True,
        "label_source": "synthetic_seed",
        "production_eligible": False,
        "production_authorized": False,
        "human_metrics": None,
        "dataset": audit,
        "epochs": args.epochs,
        "examples_seen": seen,
        "optimizer_updates": updates,
        "microbatches": steps,
        "batch_size": 4,
        "gradient_accumulation": 8,
        "dataloader_num_workers": 0,
        "max_length": 192,
        "r": 16,
        "lora_alpha": 32,
        "precision": str(precision),
        "original_vocabulary": original_vocab,
        "special_tokens_trainable": list(tokenizer.additional_special_tokens),
        "encoder_outputs": ["bio_logits", "segment_logits", "pooled"],
        "team_head_inside_onnx": False,
        "weighted_loss_first": losses[0],
        "weighted_loss_last": losses[-1],
        "elapsed_seconds": time.perf_counter() - begin,
        "telemetry_samples": telemetry,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "peft", "numpy", "onnx", "onnxruntime")
        },
    }
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    gc.collect()
    torch.cuda.empty_cache()
    guard.close()
    print("Pinned pretrained LoRA training completed; synthetic provenance, production unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
