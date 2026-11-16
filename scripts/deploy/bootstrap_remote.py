"""Run the idempotent bootstrap (roles, migrations, synthetic tenant) against the hosted Neon DB.

Reads artifacts/deploy/{prod,neon}.env; prints nothing secret.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]


def read_env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in path.read_text(encoding="utf-8-sig").splitlines() if "=" in line
    )


def main() -> int:
    prod = read_env(ROOT / "artifacts/deploy/prod.env")
    owner = read_env(ROOT / "artifacts/deploy/neon.env")["NEON_OWNER_DSN"].strip()
    parts = urlsplit(owner)

    def url(user: str, password: str) -> str:
        return urlunsplit(
            ("postgresql+asyncpg", f"{user}:{password}@{parts.hostname}", parts.path, "ssl=require", "")
        )

    env = dict(
        os.environ,
        RESOLVEIT_ADMIN_DSN=owner,
        RESOLVEIT_MIGRATOR_DATABASE_URL=url("resolveit_migrator", prod["RESOLVEIT_MIGRATOR_PASSWORD"]),
        **{
            k: prod[k]
            for k in (
                "RESOLVEIT_MIGRATOR_PASSWORD",
                "RESOLVEIT_APP_PASSWORD",
                "RESOLVEIT_API_KEY",
                "RESOLVEIT_AGENT_KEY",
            )
        },
    )
    return subprocess.call([sys.executable, "scripts/bootstrap_db.py"], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
