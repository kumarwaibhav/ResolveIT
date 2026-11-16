"""Block-wise INT8 weights (MatMulNBits, bits=8) with block-wise activation quantization.

Per-tensor dynamic activation quantization failed parity (outlier channels). Here each
32-element block gets its own scale, so an outlier only costs precision inside its block.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import onnx  # noqa: E402
from onnxruntime.quantization.matmul_nbits_quantizer import (  # noqa: E402
    DefaultWeightOnlyQuantConfig,
    MatMulNBitsQuantizer,
)

from training.parity_probe import TEXTS  # noqa: E402
from training.quant_sweep import FP32, OUT, compare, timing  # noqa: E402
from training.release_bundle import feed, session, tokenizer_for  # noqa: E402


def build(target: Path, level: int, block: int) -> None:
    model = onnx.load(str(FP32))
    config = DefaultWeightOnlyQuantConfig(block_size=block, is_symmetric=True, accuracy_level=level, bits=8)
    q = MatMulNBitsQuantizer(model, algo_config=config)
    q.process()
    q.model.save_model_to_file(str(target), use_external_data_format=False)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tok = tokenizer_for(ROOT / "artifacts/release_candidate_bundle")
    feeds = [feed(tok, t) for t in TEXTS]
    ref = session(FP32, 4)
    expected = [ref.run(None, f) for f in feeds]
    del ref
    for level, block in ((4, 32), (4, 128), (0, 32)):
        name = f"nbits8_l{level}_b{block}"
        target = OUT / f"{name}.onnx"
        build(target, level, block)
        s = session(target, 4)
        res = {**compare(expected, [s.run(None, f) for f in feeds])}
        del s
        res["latency"] = timing(target, tok)
        res["mb"] = round(target.stat().st_size / 2**20)
        print(json.dumps({name: res}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
