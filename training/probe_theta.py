"""Which head_train texts make the rules extract a service that disagrees with the label."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from resolveit_core.frame.merger import frame_from_rules  # noqa: E402
from resolveit_core.rules.engine import run_rules  # noqa: E402
from resolveit_core.schemas import Slot  # noqa: E402

from training.data import load as load_seed  # noqa: E402
from training.release_bundle import FIXED_TIME, assemble  # noqa: E402

rows = assemble(
    load_seed(ROOT / "artifacts/training/multilingual.jsonl"),
    [json.loads(x) for x in (ROOT / "artifacts/training/freetext.jsonl").read_text("utf-8").splitlines()],
)
seen = collections.Counter()
for row in rows["head_train"]:
    frame = frame_from_rules(run_rules(row["text"], FIXED_TIME, "Asia/Kolkata"))
    svc = next((s.value for s in frame.slots if s.slot == Slot.SERVICE and s.value), None)
    if svc == "printer" and row.get("team") not in ("Hardware_Endpoint",):
        seen[row.get("team")] += 1
        if seen[row.get("team")] <= 2:
            print(row.get("team"), row.get("kind"), row["text"][:160])
print(dict(seen))
