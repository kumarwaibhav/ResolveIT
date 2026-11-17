"""Database access. `tenant_tx` is the only way application code gets a session.

Each call opens one transaction and sets the tenant with a transaction-scoped
set_config, so the setting cannot outlive the transaction, leak to the next user
of a pooled connection, or leak to another client behind PgBouncer transaction
pooling. Disabled statement caches keep asyncpg safe behind that pooler.

Connections are pooled and reused. Opening one per transaction (the old NullPool)
paid a full TCP + TLS + SCRAM handshake every time, about a second against Neon,
and a ticket makes several transactions. pre_ping replaces connections the server
dropped (Neon suspends idle compute); recycle retires them before that happens.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=240,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
            },
        )
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    @asynccontextmanager
    async def tenant_tx(self, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        if not isinstance(tenant_id, UUID):
            raise TypeError("tenant_id must be a UUID from a verified credential")
        async with self._sessions() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
            )
            yield session

    async def resolve_api_key(self, key_hash: str) -> tuple[UUID, str, UUID | None] | None:
        """Pre-tenant lookup through the SECURITY DEFINER function; reads nothing else."""
        async with self._sessions() as session, session.begin():
            row = (
                await session.execute(
                    text("SELECT tenant_id, role, human_subject_id FROM resolve_api_key(:h)"), {"h": key_hash}
                )
            ).first()
        return (row[0], row[1], row[2]) if row else None

    async def due_clarifications(self, limit: int = 100) -> list[tuple[UUID, UUID]]:
        """(tenant_id, incident_id) pairs past their clarification deadline. IDs only, all tenants."""
        async with self._sessions() as session, session.begin():
            rows = (
                await session.execute(
                    text("SELECT tenant_id, incident_id FROM due_clarifications(:n)"), {"n": limit}
                )
            ).all()
        return [(r[0], r[1]) for r in rows]

    async def due_outbox(self, limit: int = 100) -> list[tuple[UUID, UUID]]:
        async with self._sessions() as session, session.begin():
            rows = (
                await session.execute(text("SELECT tenant_id, event_id FROM due_outbox(:n)"), {"n": limit})
            ).all()
        return [(r[0], r[1]) for r in rows]

    @asynccontextmanager
    async def leader_lock(self, lock_id: int) -> AsyncIterator[bool]:
        """Session advisory lock so only one worker drains at a time.

        Needs a direct Postgres connection: session locks do not survive PgBouncer
        transaction pooling. Yields False if another worker holds the lock.
        """
        async with self._engine.connect() as conn:
            got = bool((await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_id})).scalar())
            await conn.commit()
            try:
                yield got
            finally:
                if got:
                    await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_id})
                    await conn.commit()

    async def dispose(self) -> None:
        await self._engine.dispose()


__all__ = ["Database"]
