"""At-least-once outbox delivery with fencing leases and bounded retries.

An external connector must honor event_id as its idempotency key. A crash after
remote acceptance but before acknowledgement can redeliver; exactly-once remote
delivery is impossible without the receiver's idempotency contract.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text


class RouteTransport(Protocol):
    async def deliver(self, event_id: UUID, tenant_id: UUID, payload: dict[str, Any]) -> None: ...


async def drain(db: Any, transport: RouteTransport, limit: int = 100) -> tuple[int, int]:
    delivered = failed = 0
    for tenant_id, event_id in await db.due_outbox(limit):
        token = uuid4()
        async with db.tenant_tx(tenant_id) as session:
            await session.execute(
                text(
                    "UPDATE outbox SET status='dead', lease_token=NULL, lease_until=NULL "
                    "WHERE id=:id AND attempts>=8 AND status='leased' AND lease_until<=now()"
                ),
                {"id": event_id},
            )
            row = (
                await session.execute(
                    text(
                        "UPDATE outbox SET status='leased', lease_token=:token, lease_until=now()+interval "
                        "'2 minutes', attempts=attempts+1 WHERE id=:id AND attempts<8 AND "
                        "((status='pending' AND available_at<=now()) OR (status='leased' AND "
                        "lease_until<=now())) RETURNING payload, attempts"
                    ),
                    {"id": event_id, "token": token},
                )
            ).first()
            if row is None:
                continue
        try:
            await transport.deliver(event_id, tenant_id, row[0])
        except Exception:
            failed += 1
            async with db.tenant_tx(tenant_id) as session:
                await session.execute(
                    text(
                        "UPDATE outbox SET status=CASE WHEN attempts>=8 THEN 'dead' ELSE 'pending' END, "
                        "available_at=now()+make_interval(secs=>LEAST(3600, power(2, attempts)::integer)), "
                        "lease_token=NULL, lease_until=NULL WHERE id=:id AND lease_token=:token"
                    ),
                    {"id": event_id, "token": token},
                )
        else:
            async with db.tenant_tx(tenant_id) as session:
                result = await session.execute(
                    text(
                        "UPDATE outbox SET status='delivered', delivered_at=now(), lease_token=NULL, "
                        "lease_until=NULL WHERE id=:id AND lease_token=:token RETURNING id"
                    ),
                    {"id": event_id, "token": token},
                )
                delivered += int(result.first() is not None)
    return delivered, failed
