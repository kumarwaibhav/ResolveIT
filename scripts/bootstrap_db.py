"""Idempotent local-demo database initialization. Not a production provisioner."""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import sys
from uuid import UUID

import asyncpg

DEMO_ID = UUID("00000000-0000-4000-8000-000000000001")


async def bootstrap() -> None:
    admin = await asyncpg.connect(os.environ["RESOLVEIT_ADMIN_DSN"])
    for name, password, attrs in (
        ("resolveit_migrator", os.environ["RESOLVEIT_MIGRATOR_PASSWORD"], "CREATEROLE"),
        ("resolveit_app", os.environ["RESOLVEIT_APP_PASSWORD"], "NOCREATEROLE"),
    ):
        # Only generated URL-safe passwords and fixed identifiers enter DDL.
        if not password or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in password
        ):
            raise ValueError("Bootstrap requires generated URL-safe passwords")
        if not await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", name):
            await admin.execute(
                f"CREATE ROLE {name} LOGIN NOSUPERUSER NOBYPASSRLS {attrs} PASSWORD '{password}'"
            )
    if not await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname='resolveit_auth'"):
        await admin.execute("CREATE ROLE resolveit_auth NOLOGIN NOSUPERUSER BYPASSRLS")
    await admin.execute("GRANT resolveit_auth TO resolveit_migrator WITH ADMIN OPTION")
    database_name = await admin.fetchval("SELECT quote_ident(current_database())")
    await admin.execute(f"ALTER DATABASE {database_name} OWNER TO resolveit_migrator")
    await admin.close()
    await asyncio.to_thread(subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    conn = await asyncpg.connect(
        os.environ["RESOLVEIT_MIGRATOR_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    )
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(DEMO_ID))
        await conn.execute(
            "INSERT INTO tenants(id,name,is_synthetic) VALUES($1,'Synthetic Demo Co',true) "
            "ON CONFLICT(id) DO NOTHING",
            DEMO_ID,
        )
        for role, variable in (("admin", "RESOLVEIT_API_KEY"), ("agent", "RESOLVEIT_AGENT_KEY")):
            digest = hashlib.sha256(os.environ[variable].encode()).hexdigest()
            await conn.execute(
                "INSERT INTO api_keys(id,tenant_id,key_hash,role) VALUES(gen_random_uuid(),$1,$2,$3) "
                "ON CONFLICT(key_hash) DO NOTHING",
                DEMO_ID,
                digest,
                role,
            )
        await conn.execute(
            "INSERT INTO channel_stats(tenant_id,channel,asks,answers) "
            "VALUES($1,'web',20,16),($1,'agent',20,16) ON CONFLICT DO NOTHING",
            DEMO_ID,
        )
    await conn.close()
    print("Migrated database; synthetic tenant ready. Credentials withheld.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
