from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import text

from .conftest import TENANT_A, TENANT_B, auth

TABLES = [
    "tenants",
    "api_keys",
    "incidents",
    "incident_keys",
    "incident_text",
    "subject_index",
    "frames",
    "decisions",
    "questions",
    "channel_stats",
    "erasure_requests",
    "mcp_calls",
]


async def _create(client: httpx.AsyncClient, key: str, body: str) -> dict:
    r = await client.post("/v1/incidents", json={"text": body}, headers=auth(key))
    assert r.status_code == 201, r.text
    return r.json()


async def test_every_table_has_rls_enabled_forced_and_a_policy(app_conn: asyncpg.Connection) -> None:
    """Checks every table in the schema, so a new table cannot ship without isolation."""
    rows = await app_conn.fetch(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
        "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    )
    assert {r["relname"] for r in rows} >= set(TABLES)
    for r in rows:
        assert r["relrowsecurity"] and r["relforcerowsecurity"] and r["policies"] == 1, r["relname"]


async def test_app_role_is_not_privileged(app_conn: asyncpg.Connection) -> None:
    row = await app_conn.fetchrow(
        "SELECT rolsuper, rolbypassrls, rolcreaterole FROM pg_roles WHERE rolname = current_user"
    )
    assert not row["rolsuper"] and not row["rolbypassrls"] and not row["rolcreaterole"]
    owners = await app_conn.fetch("SELECT tableowner FROM pg_tables WHERE schemaname = 'public'")
    assert {r["tableowner"] for r in owners} == {"resolveit_migrator"}


async def test_no_tenant_set_reads_nothing_and_cannot_write(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    await _create(client, "a_admin", "VPN is down")
    for table in TABLES:
        assert await app_conn.fetchval(f"SELECT count(*) FROM {table}") == 0, table
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await app_conn.execute("INSERT INTO tenants (id, name) VALUES ($1, 'intruder')", uuid4())
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await app_conn.execute("SELECT * FROM resolve_api_key('x'); SET ROLE resolveit_auth")


async def test_tenant_cannot_write_rows_for_another_tenant(app_conn: asyncpg.Connection) -> None:
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_A))
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await app_conn.execute(
                "INSERT INTO channel_stats (tenant_id, channel) VALUES ($1, 'web')", TENANT_B
            )


async def test_setting_does_not_outlive_the_transaction(app_conn: asyncpg.Connection) -> None:
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_A))
        assert await app_conn.fetchval("SELECT count(*) FROM tenants") == 1
    assert await app_conn.fetchval("SELECT count(*) FROM tenants") == 0


async def test_cross_tenant_api_access_is_404_not_403(client: httpx.AsyncClient) -> None:
    mine = await _create(client, "a_admin", "Outlook keeps crashing")
    assert (await client.get(f"/v1/incidents/{mine['id']}", headers=auth("a_admin"))).status_code == 200
    assert (await client.get(f"/v1/incidents/{mine['id']}", headers=auth("b_admin"))).status_code == 404
    r = await client.post(
        f"/v1/incidents/{mine['id']}/answer", json={"answer": None}, headers=auth("b_admin")
    )
    assert r.status_code == 404


async def test_200_concurrent_mixed_tenant_transactions_never_cross(client: httpx.AsyncClient) -> None:
    await _create(client, "a_admin", "printer jam")
    await _create(client, "b_admin", "wifi slow")
    db = client.app.state.db  # type: ignore[attr-defined]

    async def read(tenant: UUID) -> set[UUID]:
        async with db.tenant_tx(tenant) as session:
            await asyncio.sleep(0)
            rows = (await session.execute(text("SELECT tenant_id FROM incidents"))).all()
            return {r[0] for r in rows}

    tenants = [TENANT_A if i % 2 else TENANT_B for i in range(200)]
    sem = asyncio.Semaphore(20)

    async def guarded(t: UUID) -> set[UUID]:
        async with sem:
            return await read(t)

    results = await asyncio.gather(*(guarded(t) for t in tenants))
    for tenant, seen in zip(tenants, results, strict=True):
        assert seen == {tenant}


async def test_auth_failures(client: httpx.AsyncClient) -> None:
    assert (await client.post("/v1/incidents", json={"text": "x"})).status_code == 401
    assert (await client.post("/v1/incidents", json={"text": "x"}, headers=auth("nope"))).status_code == 401
    assert (
        await client.post("/v1/incidents", json={"text": "x"}, headers=auth("a_viewer"))
    ).status_code == 403
    r = await client.post(
        "/v1/privacy/erasure", json={"kind": "EMAIL", "identifier": "a@b.in"}, headers=auth("a_viewer")
    )
    assert r.status_code == 403
    r = await client.post(
        "/v1/incidents", json={"text": "x", "tenant_id": str(TENANT_B)}, headers=auth("a_admin")
    )
    assert r.status_code == 422  # a tenant cannot be named in the body at all
