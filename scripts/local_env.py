"""Generate private local-demo environment once; never overwrite existing keys."""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    target = ROOT / ".env"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    present = {line.split("=", 1)[0].strip() for line in existing.splitlines() if "=" in line}
    values = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "RESOLVEIT_APP_PASSWORD": secrets.token_urlsafe(32),
        "RESOLVEIT_MIGRATOR_PASSWORD": secrets.token_urlsafe(32),
        "RESOLVEIT_MASTER_KEY_B64": base64.b64encode(secrets.token_bytes(32)).decode(),
        "RESOLVEIT_SESSION_KEY_B64": base64.b64encode(secrets.token_bytes(32)).decode(),
        "RESOLVEIT_API_KEY": "rit_" + secrets.token_urlsafe(32),
        "RESOLVEIT_AGENT_KEY": "rit_" + secrets.token_urlsafe(32),
        "RESOLVEIT_LOCAL_DEMO": "true",
    }
    missing = {key: value for key, value in values.items() if key not in present}
    if not missing:
        print("Existing .env preserved; no missing settings.")
        return
    with target.open("a" if target.exists() else "x", encoding="utf-8", newline="\n") as output:
        if existing and not existing.endswith("\n"):
            output.write("\n")
        if not existing:
            output.write("# Generated local synthetic demo secrets. Never commit or publish.\n")
        output.writelines(f"{key}={value}\n" for key, value in missing.items())
    if os.name != "nt":
        target.chmod(0o600)
    print("Private .env ready; existing values preserved, new values withheld.")


if __name__ == "__main__":
    main()
