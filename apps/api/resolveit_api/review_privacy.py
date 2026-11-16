"""Immutable human annotation exposure records; identity is never supplied by clients."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_exposure(
    session: AsyncSession, tenant_id: UUID, incident_id: UUID, subject: UUID | None, kind: str = "model"
) -> None:
    if subject is not None:
        await session.execute(
            text(
                "INSERT INTO review_exposures (tenant_id,incident_id,subject_id,kind) "
                "SELECT :t,:i,:s,:k WHERE EXISTS (SELECT 1 FROM review_items WHERE incident_id=:i) "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": tenant_id, "i": incident_id, "s": subject, "k": kind},
        )
