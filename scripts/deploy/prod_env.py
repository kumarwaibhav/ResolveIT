"""Generate fresh production secrets for the hosted deployment (never the local dev values).

Writes artifacts/deploy/prod.env (gitignored) and prints only the variable NAMES. Re-running
keeps existing values: rotating RESOLVEIT_MASTER_KEY_B64 would make stored tickets unreadable.
"""

from __future__ import annotations

import base64
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/deploy/prod.env"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    current: dict[str, str] = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                name, value = line.split("=", 1)
                current[name] = value
    fresh = {
        "RESOLVEIT_MASTER_KEY_B64": base64.b64encode(secrets.token_bytes(32)).decode(),
        "RESOLVEIT_SESSION_KEY_B64": base64.b64encode(secrets.token_bytes(32)).decode(),
        "RESOLVEIT_API_KEY": "rit_" + secrets.token_urlsafe(32),
        "RESOLVEIT_AGENT_KEY": "rit_" + secrets.token_urlsafe(32),
        "RESOLVEIT_MIGRATOR_PASSWORD": secrets.token_urlsafe(24),
        "RESOLVEIT_APP_PASSWORD": secrets.token_urlsafe(24),
    }
    for name, value in fresh.items():
        current.setdefault(name, value)
    OUT.write_text("".join(f"{k}={v}\n" for k, v in current.items()), encoding="utf-8")
    print("prod.env holds:", ", ".join(sorted(current)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
