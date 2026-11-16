"""Five-layer inbound guard for a configured Jira connector.

Jira's X-Hub-Signature authenticates raw bytes. Delivery IDs are not signed,
so inbox deduplication also binds the body digest. Signature verification must
precede decoding. Actor/marker/state checks are additional echo defenses, never
authentication. No external Jira requests are made by this module.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def verify_signature(secret: bytes, body: bytes, signature: str) -> str:
    if not secret or len(body) > 1_048_576:
        raise ValueError("webhook secret missing or body too large")
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("invalid Jira webhook signature")
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True, slots=True)
class JiraChange:
    """Metadata extracted from an authenticated body by the configured field mapper."""

    event_id: str
    actor_id: str
    origin_marker: str | None
    assignment: str | None
    sequence: int


async def accept_change(
    session: AsyncSession,
    tenant_id: UUID,
    change: JiraChange,
    body_hash: str,
    *,
    integration_actor: str,
    expected_origin: str | None,
    current_assignment: str | None,
    last_sequence: int,
) -> str:
    """Call in the same tenant transaction as state updates; caller locks connector state.

    Layers: verified signature (before call), durable event/body deduplication,
    bot actor exclusion, our write marker exclusion, stale/no-op state exclusion.
    This does not infer an assignment from ticket text or create an outbox event.
    """
    if not change.event_id or len(change.event_id) > 200 or len(body_hash) != 64:
        raise ValueError("invalid webhook identity")
    disposition = "accepted"
    if integration_actor and change.actor_id == integration_actor:
        disposition = "integration_actor"
    elif expected_origin is not None and change.origin_marker == expected_origin:
        disposition = "origin_marker"
    elif change.sequence <= last_sequence or change.assignment == current_assignment:
        disposition = "stale_or_noop"
    row = (
        await session.execute(
            text(
                "INSERT INTO inbox (tenant_id, source, event_id, body_hash, disposition) "
                "VALUES (:t,'jira',:id,:h,:d) ON CONFLICT DO NOTHING RETURNING event_id"
            ),
            {"t": tenant_id, "id": change.event_id, "h": body_hash, "d": disposition},
        )
    ).first()
    return disposition if row is not None else "duplicate"
