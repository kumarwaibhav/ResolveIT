"""Native loopback synthetic demo using the task-owned audit PostgreSQL container.

Run prepare, then api and web in separate terminals. Existing database and private
keys are preserved. This is a local audit/demo launcher, not production deployment.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
from gpu_guard import ResourceGuard

ROOT = Path(__file__).resolve().parents[1]


def environment() -> dict[str, str]:
    result = dict(os.environ)
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            result[name] = value
    # The pinned bundle id must come from .env (the trusted release channel), never from the
    # bundle's own manifest; without it the API serves the rule-only synthetic bundle.
    result.setdefault("RESOLVEIT_BUNDLE_DIR", str(ROOT / "artifacts/release_candidate_bundle"))
    result.setdefault("RESOLVEIT_ENCODER_THREADS", "4")
    result.update(
        {
            "RESOLVEIT_ADMIN_DSN": "postgresql://postgres@127.0.0.1:54329/resolveit_demo",
            "RESOLVEIT_MIGRATOR_DATABASE_URL": "postgresql+asyncpg://resolveit_migrator:mig_dev_pw@127.0.0.1:54329/resolveit_demo",
            "RESOLVEIT_APP_DATABASE_URL": "postgresql+asyncpg://resolveit_app:app_dev_pw@127.0.0.1:54329/resolveit_demo",
            "RESOLVEIT_API_URL": "http://127.0.0.1:8000",
            "RESOLVEIT_LOCAL_DEMO": "true",
            "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ("apps/api", "apps/worker", "enterprise")),
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "NODE_OPTIONS": "--max-old-space-size=512",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
    )
    return result


async def prepare(env: dict[str, str]) -> None:
    conn = await asyncpg.connect("postgresql://postgres@127.0.0.1:54329/postgres")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname='resolveit_demo'")
        if not exists:
            await conn.execute("CREATE DATABASE resolveit_demo OWNER resolveit_migrator")
    finally:
        await conn.close()
    await asyncio.to_thread(
        subprocess.run, [sys.executable, "scripts/bootstrap_db.py"], cwd=ROOT, env=env, check=True
    )
    names = (
        "RESOLVEIT_LOCAL_DEMO",
        "RESOLVEIT_API_URL",
        "RESOLVEIT_API_KEY",
        "RESOLVEIT_AGENT_KEY",
        "RESOLVEIT_SESSION_KEY_B64",
    )
    target = ROOT / "apps/web/.env.local"
    if target.exists():
        existing = dict(
            line.split("=", 1)
            for line in target.read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        if any(existing.get(name) not in (None, env[name]) for name in names):
            raise RuntimeError(
                "Existing web .env.local differs; preserved. Configure audit environment manually."
            )
    target.write_text("".join(f"{name}={env[name]}\n" for name in names), encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)
    print("Native synthetic database and private web environment ready; values withheld.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "api", "web"))
    args = parser.parse_args()
    ResourceGuard(exclusive=args.action == "prepare").checkpoint()
    env = environment()
    if args.action == "prepare":
        asyncio.run(prepare(env))
        return 0
    command = (
        [
            sys.executable,
            "-m",
            "uvicorn",
            "resolveit_api.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ]
        if args.action == "api"
        else ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "-p", "3000"]
    )
    cwd = ROOT if args.action == "api" else ROOT / "apps/web"
    return subprocess.call(
        [sys.executable, str(ROOT / "scripts/gpu_guard.py"), "--shared", "--", *command], cwd=cwd, env=env
    )


if __name__ == "__main__":
    raise SystemExit(main())
