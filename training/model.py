"""Three-output shared encoder; team classification deliberately stays in NumPy."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Public pinned downloads must never trigger the library's remote conversion bot.
os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "true"

import torch
from huggingface_hub import snapshot_download
from peft import LoraConfig, PeftModel, get_peft_model
from resolveit_core.masking.pii_shield import SPECIAL_TOKENS
from resolveit_core.schemas import SLOTS
from torch import nn
from transformers import AutoModel, AutoTokenizer

MODEL_ID = "microsoft/mdeberta-v3-base"
REVISION = "a0484667b22365f84929a935b5e50a51f71f159d"


def cached_snapshot() -> str:
    """Resolve the pinned local tree before tokenizer code can probe a remote ID."""
    return snapshot_download(MODEL_ID, revision=REVISION, local_files_only=True, token=False)


class Encoder(nn.Module):
    def __init__(self, backbone: Any, hidden: int) -> None:
        super().__init__()
        self.backbone = backbone
        self.bio = nn.Linear(hidden, 1 + 2 * len(SLOTS))
        self.boundary = nn.Linear(hidden, 2)

    def forward(self, input_ids: Any, attention_mask: Any) -> tuple[Any, Any, Any]:
        hidden = self.backbone(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
        return self.bio(hidden), self.boundary(hidden), pooled


def create_training_model(checkpoint: Path | None = None) -> tuple[Encoder, Any, int]:
    snapshot = cached_snapshot()
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot,
        revision=REVISION,
        use_fast=True,
        trust_remote_code=False,
        token=False,
        local_files_only=True,
    )
    if not tokenizer.is_fast:
        raise RuntimeError("A fast offset-mapping tokenizer is mandatory")
    original = len(tokenizer)
    tokenizer.add_special_tokens({"additional_special_tokens": list(SPECIAL_TOKENS)})
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    backbone = AutoModel.from_pretrained(
        snapshot,
        revision=REVISION,
        trust_remote_code=False,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        token=False,
        use_safetensors=False,
        local_files_only=True,
    )
    backbone.resize_token_embeddings(len(tokenizer), mean_resizing=False)
    backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["query_proj", "value_proj"],
        trainable_token_indices=list(range(original, len(tokenizer))),
    )
    backbone = (
        PeftModel.from_pretrained(backbone, checkpoint / "adapter", is_trainable=True, local_files_only=True)
        if checkpoint is not None
        else get_peft_model(backbone, config)
    )
    model = Encoder(backbone, backbone.config.hidden_size).to(device="cuda", dtype=dtype)
    if checkpoint is not None:
        heads = torch.load(checkpoint / "heads.pt", map_location="cpu", weights_only=True)
        model.bio.load_state_dict(heads["bio"])
        model.boundary.load_state_dict(heads["boundary"])
    return model, tokenizer, original


def load_merged(checkpoint: Any) -> tuple[Encoder, Any]:
    tokenizer = AutoTokenizer.from_pretrained(checkpoint / "tokenizer", local_files_only=True)
    base = AutoModel.from_pretrained(
        cached_snapshot(),
        revision=REVISION,
        trust_remote_code=False,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
        local_files_only=True,
        token=False,
        use_safetensors=False,
    )
    base.resize_token_embeddings(len(tokenizer), mean_resizing=False)
    adapted = PeftModel.from_pretrained(base, checkpoint / "adapter", local_files_only=True)
    merged = adapted.merge_and_unload()
    model = Encoder(merged, merged.config.hidden_size)
    heads = torch.load(checkpoint / "heads.pt", map_location="cpu", weights_only=True)
    model.bio.load_state_dict(heads["bio"])
    model.boundary.load_state_dict(heads["boundary"])
    return model.eval(), tokenizer
