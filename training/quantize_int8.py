"""Produce the shipped INT8 encoder (see training/quantize_blockwise_dq.py for the transform).

Evidence for the choice (artifacts/training/sweep/, docs/BUILD_STATE.md):
- dynamic per-tensor INT8 quantizes activations too; mDeBERTa-v3 outlier channels wiped out
  the pooled vector (cosine to FP32 0.03);
- MatMulNBits 8-bit level 4 failed the team-probability parity gate; level 0 passed but
  dequantized every call (500 ms at 128 tokens);
- block-32 INT8 weights dequantized once at load: cosine 0.9999, 225 ms at 128 tokens,
  37 ms on a short ticket (4 threads), i.e. FP32 speed with INT8 weight storage.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.quantize_blockwise_dq import main

if __name__ == "__main__":
    raise SystemExit(main())
