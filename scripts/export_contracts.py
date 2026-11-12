"""Generate the artefacts the web app consumes from the single Python source of truth.

  apps/web/openapi.json                 OpenAPI from the FastAPI app (types are generated from it)
  apps/web/src/generated/lexicon.json   rule patterns for the browser-side detail meter

Run from the repo root:  python scripts/export_contracts.py
CI fails if the committed files differ from a fresh run.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("apps/api", "packages/resolveit-core", "enterprise", "apps/worker"):
    sys.path.insert(0, str(ROOT / p))

from resolveit_core.rules import engine  # noqa: E402
from resolveit_core.schemas import Slot  # noqa: E402

from resolveit_api.main import create_app  # noqa: E402
from resolveit_api.settings import Settings  # noqa: E402


def lexicon() -> dict[str, object]:
    entries: list[dict[str, str]] = []
    for slot, table in (
        (Slot.SERVICE, engine._SERVICES),
        (Slot.FREQUENCY, engine._FREQUENCY),
        (Slot.URGENCY, engine._URGENCY),
        (Slot.SCOPE, engine._SCOPE),
    ):
        entries += [{"slot": slot.value, "value": value, "pattern": pattern} for value, pattern in table]
    entries += [
        {"slot": Slot.ERROR_CODE.value, "value": rule_id, "pattern": pat.pattern}
        for rule_id, pat in engine._ERROR_CODES
    ]
    time_patterns = [
        engine._T_AGO,
        engine._T_SINCE_DAY,
        engine._T_ISO,
        engine._T_MORNING,
        engine._T_TODAY,
        engine._T_YESTERDAY,
        engine._T_KAL,
        engine._T_LAST_WEEK,
    ]
    entries += [
        {"slot": Slot.START_TIME.value, "value": "stated", "pattern": p.pattern} for p in time_patterns
    ]
    return {
        "note": "Generated from resolveit_core.rules.engine. Do not edit. Patterns are case-insensitive.",
        "meter_slots": [
            s.value
            for s in (
                Slot.SERVICE,
                Slot.ERROR_CODE,
                Slot.SCOPE,
                Slot.FREQUENCY,
                Slot.URGENCY,
                Slot.START_TIME,
            )
        ],
        "entries": entries,
        "security_pattern": engine._SECURITY.pattern,
    }


def main() -> None:
    app = create_app(
        Settings(
            app_database_url="postgresql+asyncpg://unused/unused",
            master_key=base64.b64decode(base64.b64encode(b"0" * 32)),
        )
    )
    web = ROOT / "apps/web"
    (web / "src/generated").mkdir(parents=True, exist_ok=True)
    (web / "openapi.json").write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    (web / "src/generated/lexicon.json").write_text(
        json.dumps(lexicon(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
