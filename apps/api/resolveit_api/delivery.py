"""Transactional delivery and billing primitives. Payloads contain IDs and routing metadata only."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def ledger_hash(
    tenant_id: UUID, sequence: int, incident_id: UUID, kind: str, at: datetime, previous: str
) -> str:
    body = json.dumps(
        [str(tenant_id), sequence, str(incident_id), kind, at.astimezone(UTC).isoformat(), previous],
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


async def append_ledger(session: AsyncSession, tenant_id: UUID, incident_id: UUID, kind: str) -> str:
    """Serialize each tenant chain; duplicate business events return their original hash."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"billing:{tenant_id}"}
    )
    existing = (
        await session.execute(
            text(
                "SELECT entry_hash FROM billing_ledger WHERE tenant_id=:t AND incident_id=:i AND "
                "event_kind=:k"
            ),
            {"t": tenant_id, "i": incident_id, "k": kind},
        )
    ).scalar_one_or_none()
    if existing is not None:
        return str(existing)
    last = (
        await session.execute(
            text("SELECT sequence, entry_hash FROM billing_ledger ORDER BY sequence DESC LIMIT 1")
        )
    ).first()
    sequence, previous = (last[0] + 1, last[1]) if last else (1, "0" * 64)
    at = datetime.now(UTC)
    digest = ledger_hash(tenant_id, sequence, incident_id, kind, at, previous)
    await session.execute(
        text(
            "INSERT INTO billing_ledger (tenant_id, sequence, incident_id, event_kind, occurred_at, "
            "previous_hash, entry_hash) VALUES (:t,:s,:i,:k,:at,:p,:h)"
        ),
        {"t": tenant_id, "s": sequence, "i": incident_id, "k": kind, "at": at, "p": previous, "h": digest},
    )
    return digest


async def enqueue_route(
    session: AsyncSession, tenant_id: UUID, incident_id: UUID, version: int, team: str
) -> None:
    payload = json.dumps({"incident_id": str(incident_id), "version": version, "team": team})
    await session.execute(
        text(
            "INSERT INTO outbox (id, tenant_id, incident_id, incident_version, topic, payload) VALUES "
            "(:id,:t,:i,:v,'incident.route',CAST(:p AS jsonb)) ON CONFLICT (tenant_id, incident_id, "
            "incident_version, topic) DO NOTHING"
        ),
        {"id": uuid4(), "t": tenant_id, "i": incident_id, "v": version, "p": payload},
    )
    await append_ledger(session, tenant_id, incident_id, "routed")


async def settle_zero_bounce(session: AsyncSession, tenant_id: UUID, limit: int = 100) -> int:
    """Settle only real tenants, 72h after routing, with no recorded bounce. Caller owns transaction."""
    rows = (
        await session.execute(
            text(
                "SELECT i.id FROM incidents i JOIN tenants t ON t.id=i.tenant_id "
                "JOIN connector_observation o ON o.tenant_id=i.tenant_id AND o.status='verified' "
                "JOIN billing_ledger b ON "
                "b.incident_id=i.id AND b.event_kind='routed' WHERE NOT t.is_synthetic AND i.state IN "
                "('ROUTED','RESOLVED') AND b.occurred_at <= now()-interval '72 hours' "
                "AND o.coverage_from<=b.occurred_at "
                "AND o.complete_through>=b.occurred_at+interval '72 hours' AND NOT EXISTS "
                "(SELECT 1 FROM billing_ledger x WHERE x.incident_id=i.id AND x.event_kind IN "
                "('bounced','zero_bounce_72h')) ORDER BY b.occurred_at LIMIT :n FOR UPDATE OF i SKIP LOCKED"
            ),
            {"n": max(0, min(limit, 1000))},
        )
    ).all()
    for row in rows:
        await append_ledger(session, tenant_id, row[0], "zero_bounce_72h")
    return len(rows)
