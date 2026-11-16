"""Set the web app's Vercel production environment variables without echoing secret values.

Usage: python scripts/deploy/vercel_env.py --api-url https://... --origin https://...
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps/web"
VERCEL = shutil.which("vercel.cmd") or shutil.which("vercel") or "vercel"


def put(name: str, value: str) -> None:
    subprocess.run([VERCEL, "env", "rm", name, "production", "--yes"], cwd=WEB, capture_output=True)
    done = subprocess.run(
        [VERCEL, "env", "add", name, "production"], cwd=WEB, input=value.encode(), capture_output=True
    )
    print(name, "set" if done.returncode == 0 else f"FAILED (exit {done.returncode})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    prod = dict(
        line.split("=", 1)
        for line in (ROOT / "artifacts/deploy/prod.env").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    put("RESOLVEIT_API_URL", args.api_url)
    put("RESOLVEIT_PUBLIC_ORIGIN", args.origin)
    put("RESOLVEIT_LOCAL_DEMO", "false")
    put("RESOLVEIT_SESSION_KEY_B64", prod["RESOLVEIT_SESSION_KEY_B64"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
