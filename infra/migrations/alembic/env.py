"""Async Alembic migrations. Supply RESOLVEIT_MIGRATOR_DATABASE_URL; never use app credentials."""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine


def run_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(
        os.environ["RESOLVEIT_MIGRATOR_DATABASE_URL"], poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=os.environ["RESOLVEIT_MIGRATOR_DATABASE_URL"], literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
