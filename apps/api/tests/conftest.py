from __future__ import annotations

import base64
import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from resolveit_core.gate.bayes_evsi import experiment_assignment

from resolveit_api.auth import hash_api_key
from resolveit_api.main import create_app
from resolveit_api.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
HOST, PORT = "127.0.0.1", int(os.environ.get("PGPORT", "54329"))
DB = "resolveit_test"
APP_URL = os.environ.get(
    "RESOLVEIT_TEST_APP_URL", f"postgresql+asyncpg://resolveit_app:app_dev_pw@{HOST}:{PORT}/{DB}"
)

TENANT_A, TENANT_B, TENANT_DEMO = uuid4(), uuid4(), uuid4()
KEYS = {
    "a_admin": (TENANT_A, "admin"),
    "a_viewer": (TENANT_A, "viewer"),
    "b_admin": (TENANT_B, "admin"),
    "demo_admin": (TENANT_DEMO, "admin"),
    "demo_agent": (TENANT_DEMO, "agent"),
    "a_review1": (TENANT_A, "reviewer"),
    "a_review1_alias": (TENANT_A, "reviewer"),
    "a_review2": (TENANT_A, "reviewer"),
    "a_judge": (TENANT_A, "admin"),
    "demo_review1": (TENANT_DEMO, "reviewer"),
    "demo_review2": (TENANT_DEMO, "reviewer"),
}
_human_one = uuid4()
HUMANS = {
    "a_review1": _human_one,
    "a_review1_alias": _human_one,
    "a_review2": uuid4(),
    "a_judge": uuid4(),
    "demo_review1": uuid4(),
    "demo_review2": uuid4(),
}


async def _migrator() -> asyncpg.Connection:
    if url := os.environ.get("RESOLVEIT_TEST_MIGRATOR_URL"):
        return await asyncpg.connect(url)
    return await asyncpg.connect(
        host=HOST, port=PORT, user="resolveit_migrator", password="mig_dev_pw", database=DB
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    if os.environ.get("RESOLVEIT_TEST_SKIP_BOOTSTRAP") != "1":
        subprocess.run(
            ["bash", str(ROOT / "infra/dev/pg_local.sh"), "start"], check=True, capture_output=True
        )
    if admin_url := os.environ.get("RESOLVEIT_TEST_ADMIN_URL"):
        admin = await asyncpg.connect(admin_url)
    else:
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
                        "INSERT INTO api_keys (id, tenant_id, key_hash, role,human_subject_id) VALUES ($1, $2, $3, $4,$5)",
                        uuid4(),
                        tid,
                        hash_api_key(key),
                        role,
                        HUMANS.get(key),
                    )
    await conn.close()
    yield


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(app_database_url=APP_URL, master_key=base64.b64decode(base64.b64encode(b"k" * 32)))


@pytest_asyncio.fixture(scope="session")
async def client(settings: Settings, database: None) -> AsyncIterator[httpx.AsyncClient]:
    # This suite asserts the rule-based demo bundle's behaviour; the trained INT8 bundle has
    # its own tests (test_trained_bundle.py), so it is never picked up from the environment here.
    with patch.dict(os.environ, {"RESOLVEIT_BUNDLE_DIR": ""}):
        app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.app = app  # type: ignore[attr-defined]
        yield c
    await app.state.db.dispose()


def auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@contextmanager
def exploratory_incident(tenant_id: UUID) -> Iterator[None]:
    """Choose a real deterministic exploration assignment; do not change gate policy."""
    candidate = uuid4()
    while not experiment_assignment(f"{tenant_id}:{candidate}")[1]:
        candidate = uuid4()
    first = True

    def next_id() -> UUID:
        nonlocal first
        if first:
            first = False
            return candidate
        return uuid4()

    with patch("resolveit_api.routes.intake.uuid4", side_effect=next_id):
        yield


@pytest_asyncio.fixture
async def app_conn() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(
        host=HOST, port=PORT, user="resolveit_app", password="app_dev_pw", database=DB
    )
    yield conn
    await conn.close()


__all__ = ["TENANT_A", "TENANT_B", "TENANT_DEMO", "UUID", "auth"]
