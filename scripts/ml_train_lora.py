"""Guarded three-head mDeBERTa LoRA training on provenance-tagged JSONL.

Optional dependencies: torch, transformers, peft, sentencepiece, safetensors.
Supply an immutable 40-character --revision. No model download/training occurs
on import. This entrypoint is separate from the synthetic fixture smoke.

Rows: text, team (TEAMS value), label_source, split='train', slots mapping
slot names to {state: PRESENT|MISSING|AMBIGUOUS|CONTRADICTED, spans:[[raw_start,raw_end]]}.
All 11 slot states are required. Raw text never enters training artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from gpu_guard import ResourceGuard
from resolveit_core.masking.pii_shield import SPECIAL_TOKENS, mask_pii
from resolveit_core.offsets.offset_map import OffsetChain, normalize_nfkc
from resolveit_core.schemas import SLOTS, TEAMS, EpistemicState


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="microsoft/mdeberta-v3-base")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4, choices=[4, 8])
    parser.add_argument("--gradient-accumulation", type=int, default=4, choices=[4, 8])
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--export-onnx", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("--revision must be an immutable Hugging Face commit hash")
    if args.epochs < 1:
        parser.error("epochs must be positive")
    # Guard runs before large imports, model download or GPU allocation.
    guard = ResourceGuard(require_gpu=not args.cpu)
    guard.checkpoint()
    import torch
    from peft import LoraConfig, get_peft_model
    from torch.nn import functional
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(2)
    torch.manual_seed(20261114)
    device = torch.device("cpu" if args.cpu else "cuda")
    if not args.cpu:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; choose --cpu explicitly")
        torch.cuda.set_per_process_memory_fraction(0.75)
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, use_fast=True,
                                             trust_remote_code=False)
    if not tokenizer.is_fast:
        raise RuntimeError("Fast tokenizer offset mapping required")
    original_vocab = len(tokenizer)
    tokenizer.add_special_tokens({"additional_special_tokens": list(SPECIAL_TOKENS)})
    encoder = AutoModel.from_pretrained(args.model, revision=args.revision, trust_remote_code=False)
    encoder.resize_token_embeddings(len(tokenizer))
    encoder.gradient_checkpointing_enable()
    config = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                        target_modules=["query_proj", "value_proj"],
                        trainable_token_indices=list(range(original_vocab, len(tokenizer))))
    encoder = get_peft_model(encoder, config)

    class ThreeHead(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = encoder
            dim = encoder.config.hidden_size
            self.team = torch.nn.Linear(dim, len(TEAMS))
            self.bio = torch.nn.Linear(dim, 1 + 2 * len(SLOTS))
            self.state = torch.nn.Linear(dim, len(SLOTS) * len(EpistemicState))

        def forward(self, input_ids: Any, attention_mask: Any) -> tuple[Any, Any, Any]:
            hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            mask = attention_mask.unsqueeze(-1)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
            return self.team(pooled), self.bio(hidden), self.state(pooled).reshape(-1, len(SLOTS), 4)

    model = ThreeHead().to(device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4)
    args.output.mkdir(parents=True, exist_ok=True)
    seen = 0

    def checkpoint() -> None:
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "examples_seen": seen, "base_revision": args.revision}, args.output / "checkpoint.pt")

    def encode(rows: list[dict[str, Any]]) -> tuple[Any, Any, Any, Any, Any]:
        texts, span_rows, states, teams, sample_weights = [], [], [], [], []
        for row in rows:
            norm, raw_map = normalize_nfkc(row["text"])
            masked = mask_pii(norm)
            chain = OffsetChain([raw_map, masked.offset_map])
            texts.append(masked.masked_text)
            span_rows.append({slot: [chain.from_raw(*span) for span in row["slots"][slot.value]["spans"]]
                              for slot in SLOTS})
            states.append([list(EpistemicState).index(EpistemicState(row["slots"][s.value]["state"]))
                           for s in SLOTS])
            teams.append([t.value for t in TEAMS].index(row["team"]))
            sample_weights.append(0.3 if row["label_source"] == "llm_silver" else 1.0)
        encoded = tokenizer(texts, padding=True, truncation=True, max_length=192,
                            return_offsets_mapping=True, return_tensors="pt")
        offsets = encoded.pop("offset_mapping").tolist()
        token_labels = torch.full_like(encoded["input_ids"], -100)
        for i, spans in enumerate(span_rows):
            for token, (start, end) in enumerate(offsets[i]):
                if end <= start:
                    continue
                token_labels[i, token] = 0
                matches = [(j, a, b) for j, s in enumerate(SLOTS) for a, b in spans[s]
                           if start < b and a < end]
                if len(matches) > 1:
                    # One BIO head cannot express overlapping slot spans.
                    token_labels[i, token] = -100
                elif matches:
                    j, a, _ = matches[0]
                    token_labels[i, token] = 1 + 2 * j + int(start > a)
        inputs = {k: v.to(device) for k, v in encoded.items() if k in ("input_ids", "attention_mask")}
        return (inputs, torch.tensor(teams, device=device), token_labels.to(device),
                torch.tensor(states, device=device), torch.tensor(sample_weights, device=device))

    model.train()
    optimizer.zero_grad()
    steps = 0
    for _ in range(args.epochs):
        batch: list[dict[str, Any]] = []
        with args.data.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row.get("split") != "train":
                    continue
                if row.get("label_source") not in {
                    "llm_silver", "human_correction", "human_gold", "synthetic_seed"
                }:
                    raise ValueError("Unknown or absent label provenance")
                batch.append(row)
                if len(batch) < args.batch_size:
                    continue
                guard.checkpoint(save=checkpoint)
                inputs, team_y, bio_y, state_y, weights = encode(batch)
                mixed_precision = device.type == "cuda" and torch.cuda.is_bf16_supported()
                with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=mixed_precision):
                    team, bio, state = model(**inputs)
                    team_loss = functional.cross_entropy(team, team_y, reduction="none")
                    bio_loss = functional.cross_entropy(bio.transpose(1, 2), bio_y, reduction="none")
                    valid = bio_y != -100
                    bio_loss = (bio_loss * valid).sum(1) / valid.sum(1).clamp_min(1)
                    state_loss = functional.cross_entropy(
                        state.transpose(1, 2), state_y, reduction="none"
                    ).mean(1)
                    loss = ((team_loss + bio_loss + state_loss) * weights).mean() / args.gradient_accumulation
                loss.backward()
                seen += len(batch)
                steps += 1
                batch.clear()
                if steps % args.gradient_accumulation == 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    optimizer.zero_grad()
                if device.type == "cuda":
                    torch.cuda.empty_cache()
    if steps == 0:
        raise ValueError("No complete training batch; at least batch-size train rows required")
    if steps % args.gradient_accumulation:
        factor = args.gradient_accumulation / (steps % args.gradient_accumulation)
        for parameter in model.parameters():
            if parameter.grad is not None:
                parameter.grad.mul_(factor)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
    checkpoint()
    encoder.save_pretrained(args.output / "adapter")
    tokenizer.save_pretrained(args.output / "tokenizer")
    if args.export_onnx:
        guard.checkpoint(save=checkpoint)
        from onnxruntime.quantization import QuantType, quantize_dynamic

        model.encoder = encoder.merge_and_unload()
        model = model.cpu().float().eval()
        dummy = tokenizer("Synthetic export shape check", return_tensors="pt")
        fp32 = args.output / "model_fp32.onnx"
        torch.onnx.export(model, (dummy["input_ids"], dummy["attention_mask"]), str(fp32),
                          input_names=["input_ids", "attention_mask"],
                          output_names=["team_logits", "bio_logits", "state_logits"],
                          dynamic_axes={"input_ids": {0: "batch", 1: "tokens"},
                                        "attention_mask": {0: "batch", 1: "tokens"},
                                        "team_logits": {0: "batch"},
                                        "bio_logits": {0: "batch", 1: "tokens"},
                                        "state_logits": {0: "batch"}}, opset_version=17, dynamo=False)
        guard.checkpoint()
        quantize_dynamic(str(fp32), str(args.output / "model_int8.onnx"),
                         weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"])
    (args.output / "training_manifest.json").write_text(json.dumps({
        "base_model": args.model, "revision": args.revision, "examples_seen": seen,
        "max_length": 192, "lora_r": 16, "lora_alpha": 32,
        "heads": ["team", "BIO spans", "11-slot epistemic state"],
        "production_eligible": False, "calibration_required": True,
        "human_test_metrics": None,
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
