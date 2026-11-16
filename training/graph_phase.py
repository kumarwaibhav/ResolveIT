"""Isolated heavyweight graph phases: Torch must exit before ORT quantization."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("HF_HOME", str(ROOT / "artifacts/cache/huggingface"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "true"

from gpu_guard import ResourceGuard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("export", "quantize", "validate"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    guard = ResourceGuard()
    guard.checkpoint()
    if args.phase == "export":
        import torch

        from training.model import load_merged

        torch.set_num_threads(2)
        model, tokenizer = load_merged(args.checkpoint)
        dummy = tokenizer("Synthetic export shape check", return_tensors="pt")
        with torch.inference_mode():
            torch.onnx.export(
                model,
                (dummy["input_ids"], dummy["attention_mask"]),
                str(args.output / "model_fp32.onnx"),
                input_names=["input_ids", "attention_mask"],
                output_names=["bio_logits", "segment_logits", "pooled"],
                dynamic_axes={
                    "input_ids": {0: "batch", 1: "tokens"},
                    "attention_mask": {0: "batch", 1: "tokens"},
                    "bio_logits": {0: "batch", 1: "tokens"},
                    "segment_logits": {0: "batch", 1: "tokens"},
                    "pooled": {0: "batch"},
                },
                opset_version=17,
                dynamo=False,
                external_data=True,
            )
    elif args.phase == "quantize":
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(
            str(args.output / "model_fp32.onnx"),
            str(args.output / "model_int8.onnx"),
            weight_type=QuantType.QInt8,
            op_types_to_quantize=["MatMul"],
        )
    else:
        import onnx

        for name in ("model_fp32.onnx", "model_int8.onnx"):
            onnx.checker.check_model(str(args.output / name))
    guard.close()
    print(f"Isolated graph phase {args.phase} completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
