from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from resolveit_worker.outbox import drain
from sqlalchemy import text

import resolveit_api.delivery as delivery
from resolveit_api.delivery import append_ledger, ledger_hash, settle_zero_bounce
from resolveit_api.jira_guard import JiraChange, accept_change, verify_signature

from .conftest import TENANT_A, TENANT_B, TENANT_DEMO, _migrator, auth


async def test_route_outbox_and_ledger_atomic(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    incident = (
        await client.post(
            "/v1/incidents", json={"text": "database down [outbox]"}, headers=auth("demo_admin")
        )
    ).json()
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_DEMO))
        row = await app_conn.fetchrow("SELECT payload FROM outbox WHERE incident_id=$1", UUID(incident["id"]))
        assert row and "database down" not in row[0] and "Database" in row[0]
        assert (
            await app_conn.fetchval(
                "SELECT count(*) FROM billing_ledger WHERE incident_id=$1 AND event_kind='routed'",
                UUID(incident["id"]),
            )
            == 1
        )


async def test_outbox_delivers_with_stable_id(client: httpx.AsyncClient) -> None:
    class Transport:
        def __init__(self) -> None:
            self.ids: set[UUID] = set()

        async def deliver(self, event_id: UUID, tenant_id: UUID, payload: dict[str, Any]) -> None:
            assert set(payload) == {"incident_id", "version", "team"}
            self.ids.add(event_id)

    transport = Transport()
    db = client.app.state.db  # type: ignore[attr-defined]
    delivered, failed = await drain(db, transport)
    assert delivered == len(transport.ids) and delivered > 0 and failed == 0
    assert await drain(db, transport) == (0, 0)


async def test_ledger_chain_is_tenant_bound_and_append_only(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_DEMO))
        rows = await app_conn.fetch("SELECT * FROM billing_ledger ORDER BY sequence")
        previous = "0" * 64
        for sequence, row in enumerate(rows, 1):
            assert row["sequence"] == sequence and row["previous_hash"] == previous
            previous = ledger_hash(
                TENANT_DEMO, sequence, row["incident_id"], row["event_kind"], row["occurred_at"], previous
            )
            assert row["entry_hash"] == previous
        assert rows
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_conn.execute("UPDATE billing_ledger SET entry_hash='tampered'")


async def test_composite_fk_rejects_cross_tenant_reference(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    incident = (
        await client.post("/v1/incidents", json={"text": "wifi issue"}, headers=auth("a_admin"))
    ).json()
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_B))
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await app_conn.execute(
                "INSERT INTO frames (incident_id, tenant_id, version, slots) VALUES ($1,$2,987,'{}')",
                UUID(incident["id"]),
                TENANT_B,
            )


async def test_72h_window_and_synthetic_exclusion(client: httpx.AsyncClient) -> None:
    db = client.app.state.db  # type: ignore[attr-defined]
    async with db.tenant_tx(TENANT_A) as session:
        incident_id = uuid4()
        await session.execute(
            text(
                "INSERT INTO incidents (id,tenant_id,state,channel,sla_started_at,audit_selected,no_ask_holdout) VALUES (:i,:t,'ROUTED','web',now(),false,false)"
            ),
            {"i": incident_id, "t": TENANT_A},
        )
        await append_ledger(session, TENANT_A, incident_id, "routed")
        assert await settle_zero_bounce(session, TENANT_A) == 0
    async with db.tenant_tx(TENANT_DEMO) as session:
        assert await settle_zero_bounce(session, TENANT_DEMO) == 0


async def test_billing_requires_complete_observation_and_excludes_bounces(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, app_conn: asyncpg.Connection
) -> None:
    db = client.app.state.db  # type: ignore[attr-defined]
    routed_at = datetime.now(UTC) - timedelta(hours=73)
    old_id, bounced_id, synthetic_id = uuid4(), uuid4(), uuid4()
    for tenant, incident in ((TENANT_A, old_id), (TENANT_A, bounced_id), (TENANT_DEMO, synthetic_id)):
        async with db.tenant_tx(tenant) as session:
            await session.execute(
                text(
                    "INSERT INTO incidents (id,tenant_id,state,channel,sla_started_at,audit_selected,no_ask_holdout) VALUES (:i,:t,'ROUTED','web',:at,false,false)"
                ),
                {"i": incident, "t": tenant, "at": routed_at},
            )

            class HistoricalClock:
                @staticmethod
                def now(tz: Any = None) -> datetime:
                    return routed_at

            with monkeypatch.context() as context:
                context.setattr(delivery, "datetime", HistoricalClock)
                await append_ledger(session, tenant, incident, "routed")
            if incident == bounced_id:
                await append_ledger(session, tenant, incident, "bounced")
    async with db.tenant_tx(TENANT_A) as session:
        assert await settle_zero_bounce(session, TENANT_A) == 0  # no verified connector
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(TENANT_A))
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_conn.execute(
                "INSERT INTO connector_observation (tenant_id,status,coverage_from,complete_through) VALUES ($1,'verified',$2,$3)",
                TENANT_A,
                routed_at,
                routed_at + timedelta(hours=72),
            )
    migrator = await _migrator()
    try:
        for tenant in (TENANT_A, TENANT_DEMO):
            async with migrator.transaction():
                await migrator.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tenant))
                await migrator.execute(
                    "INSERT INTO connector_observation (tenant_id,status,coverage_from,complete_through) VALUES ($1,'verified',$2,$3)",
                    tenant,
                    routed_at,
                    routed_at + timedelta(hours=72) - timedelta(microseconds=1),
                )
        async with db.tenant_tx(TENANT_A) as session:
            assert await settle_zero_bounce(session, TENANT_A) == 0  # one microsecond incomplete
        for tenant in (TENANT_A, TENANT_DEMO):
            async with migrator.transaction():
                await migrator.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tenant))
                await migrator.execute(
                    "UPDATE connector_observation SET complete_through=$1 WHERE tenant_id=$2",
                    routed_at + timedelta(hours=72),
                    tenant,
                )
        async with db.tenant_tx(TENANT_A) as session:
            assert await settle_zero_bounce(session, TENANT_A) == 1
            assert await settle_zero_bounce(session, TENANT_A) == 0  # idempotent settlement
            assert (
                await session.execute(
                    text("SELECT incident_id FROM billing_ledger WHERE event_kind='zero_bounce_72h'")
                )
            ).scalar_one() == old_id
        async with db.tenant_tx(TENANT_DEMO) as session:
            assert await settle_zero_bounce(session, TENANT_DEMO) == 0
    finally:
        await migrator.close()


async def test_jira_1000_echo_events_and_five_layers(client: httpx.AsyncClient) -> None:
    secret, body = b"test-webhook-secret", b'{"issue":{"id":"42"}}'
    signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    digest = verify_signature(secret, body, signature)
    with pytest.raises(ValueError, match="signature"):
        verify_signature(secret, body + b" ", signature)
    db = client.app.state.db  # type: ignore[attr-defined]
    async with db.tenant_tx(TENANT_A) as session:
        for i in range(1000):
            outcome = await accept_change(
                session,
                TENANT_A,
                JiraChange(f"echo-{i}", "bot", "write-1", "Network", 3),
                digest,
                integration_actor="bot",
                expected_origin="write-1",
                current_assignment="Network",
                last_sequence=2,
            )
            assert outcome == ("integration_actor" if i == 0 else "duplicate")
        for name, actor, marker, assignment, sequence, expected in [
            ("marker", "human", "write-1", "Database", 4, "origin_marker"),
            ("stale", "human", None, "Database", 1, "stale_or_noop"),
            ("noop", "human", None, "Network", 4, "stale_or_noop"),
            ("real", "human", None, "Database", 4, "accepted"),
        ]:
            unique_hash = hashlib.sha256(name.encode()).hexdigest()
            assert (
                await accept_change(
                    session,
                    TENANT_A,
                    JiraChange(name, actor, marker, assignment, sequence),
                    unique_hash,
                    integration_actor="bot",
                    expected_origin="write-1",
                    current_assignment="Network",
                    last_sequence=2,
                )
                == expected
            )


def test_hash_binds_tenant_and_timestamp() -> None:
    at = datetime.now(UTC)
    incident = uuid4()
    assert ledger_hash(TENANT_A, 1, incident, "routed", at, "0" * 64) != ledger_hash(
        TENANT_B, 1, incident, "routed", at, "0" * 64
    )
