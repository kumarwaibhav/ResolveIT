from __future__ import annotations

import base64
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

from resolveit_api.auth import hash_api_key
from resolveit_api.main import create_app
from resolveit_api.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
HOST, PORT = "127.0.0.1", int(os.environ.get("PGPORT", "54329"))
DB = "resolveit_test"
APP_URL = f"postgresql+asyncpg://resolveit_app:app_dev_pw@{HOST}:{PORT}/{DB}"

TENANT_A, TENANT_B, TENANT_DEMO = uuid4(), uuid4(), uuid4()
KEYS = {
    "a_admin": (TENANT_A, "admin"),
    "a_viewer": (TENANT_A, "viewer"),
    "b_admin": (TENANT_B, "admin"),
    "demo_admin": (TENANT_DEMO, "admin"),
    "demo_agent": (TENANT_DEMO, "agent"),
}


async def _migrator() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=HOST, port=PORT, user="resolveit_migrator", password="mig_dev_pw", database=DB
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    subprocess.run(["bash", str(ROOT / "infra/dev/pg_local.sh"), "start"], check=False, capture_output=True)
    admin = await asyncpg.connect(host=HOST, port=PORT, user="postgres", database="postgres")
    await admin.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {DB} OWNER resolveit_migrator")
    await admin.close()
    conn = await _migrator()
    for migration in sorted((ROOT / "infra/migrations").glob("*.sql")):
        await conn.execute(migration.read_text())
    for tid, name, synthetic in [
        (TENANT_A, "Acme", False),
        (TENANT_B, "Globex", False),
        (TENANT_DEMO, "Demo", True),
    ]:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tid))
            await conn.execute(
                "INSERT INTO tenants (id, name, is_synthetic) VALUES ($1, $2, $3)", tid, name, synthetic
            )
            if synthetic:
                # Synthetic response history (16 of 20 answered). With no history the gate's
                # Beta(1, 1) prior gives rho = 0.5 and asking does not pay; see README open items.
                await conn.execute(
                    "INSERT INTO channel_stats (tenant_id, channel, asks, answers) VALUES ($1, 'web', 20, 16), "
                    "($1, 'agent', 20, 16)",
                    tid,
                )
            for key, (owner, role) in KEYS.items():
                if owner == tid:
                    await conn.execute(
                        "INSERT INTO api_keys (id, tenant_id, key_hash, role) VALUES ($1, $2, $3, $4)",
                        uuid4(),
                        tid,
                        hash_api_key(key),
                        role,
                    )
    await conn.close()
    yield


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(app_database_url=APP_URL, master_key=base64.b64decode(base64.b64encode(b"k" * 32)))


@pytest_asyncio.fixture(scope="session")
async def client(settings: Settings, database: None) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.app = app  # type: ignore[attr-defined]
        yield c
    await app.state.db.dispose()


def auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest_asyncio.fixture
async def app_conn() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(
        host=HOST, port=PORT, user="resolveit_app", password="app_dev_pw", database=DB
    )
    yield conn
    await conn.close()


__all__ = ["TENANT_A", "TENANT_B", "TENANT_DEMO", "UUID", "auth"]
