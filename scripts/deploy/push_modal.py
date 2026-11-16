"""Create the Modal secret (least privilege: app DB URL + master key) and deploy infra/modal/app.py.

Reads artifacts/deploy/{prod,neon}.env; the temporary dotenv is deleted after use; prints no values.
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--web-origin", required=True)
    args = parser.parse_args()
    prod = read_env(ROOT / "artifacts/deploy/prod.env")
    parts = urlsplit(read_env(ROOT / "artifacts/deploy/neon.env")["NEON_OWNER_DSN"].strip())
    app_url = urlunsplit(
        (
            "postgresql+asyncpg",
            f"resolveit_app:{prod['RESOLVEIT_APP_PASSWORD']}@{parts.hostname}",
            parts.path,
            "ssl=require",
            "",
        )
    )
    tmp = ROOT / "artifacts/deploy/modal_secret.env"
    tmp.write_text(
        f"RESOLVEIT_APP_DATABASE_URL={app_url}\nRESOLVEIT_MASTER_KEY_B64={prod['RESOLVEIT_MASTER_KEY_B64']}\n",
        encoding="utf-8",
    )
    try:
        created = subprocess.run(
            [
                sys.executable,
                "-m",
                "modal",
                "secret",
                "create",
                "resolveit-prod",
                "--from-dotenv",
                str(tmp),
                "--force",
            ],
            capture_output=True,
        )
        print(
            "secret resolveit-prod", "created" if created.returncode == 0 else f"FAILED {created.returncode}"
        )
        if created.returncode:
            print(created.stderr.decode(errors="replace")[-400:])
            return 1
    finally:
        tmp.unlink(missing_ok=True)
    env = dict(os.environ, RESOLVEIT_BUNDLE_ID=args.bundle_id, RESOLVEIT_ALLOWED_ORIGINS=args.web_origin)
    return subprocess.call(
        [sys.executable, "-m", "modal", "deploy", str(ROOT / "infra/modal/app.py")], cwd=ROOT, env=env
    )


if __name__ == "__main__":
    raise SystemExit(main())
