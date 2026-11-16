"""Independent security tests; no inherited database fixture or production edits."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for relative in ("apps/api", "apps/worker", "enterprise", "packages/resolveit-core"):
    sys.path.insert(0, str(ROOT / relative))
