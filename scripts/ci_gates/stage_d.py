"""Run the local Stage D rehearsal under the exclusive resource governor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                str(ROOT / "scripts/gpu_guard.py"),
                "--",
                sys.executable,
                str(ROOT / "scripts/runtime_stage_d.py"),
            ],
            cwd=ROOT,
        )
    )
