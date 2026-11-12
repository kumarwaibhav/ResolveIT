"""Create a synthetic demo tenant with fresh API keys and print the web app's environment.

Usage (after migrations):  python scripts/seed_demo.py
Reads RESOLVEIT_MIGRATOR_DSN (default: the local dev cluster).
The tenant is flagged is_synthetic, so it is served only the synthetic demo bundle
and the UI shows the permanent synthetic-data banner.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from uuid import uuid4

import asyncpg

DSN = os.environ.get(
    "RESOLVEIT_MIGRATOR_DSN", "postgresql://resolveit_migrator:mig_dev_pw@127.0.0.1:54329/resolveit_dev"
)


async def main() -> None:
    conn = await asyncpg.connect(DSN)
    tenant = uuid4()
    keys = {"admin": f"rit_{secrets.token_urlsafe(32)}", "agent": f"rit_{secrets.token_urlsafe(32)}"}
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant))
        await conn.execute(
            "INSERT INTO tenants (id, name, is_synthetic) VALUES ($1, 'Synthetic Demo Co', true)", tenant
        )
        for role, key in keys.items():
            await conn.execute(
                "INSERT INTO api_keys (id, tenant_id, key_hash, role) VALUES ($1, $2, $3, $4)",
                uuid4(),
                tenant,
                hashlib.sha256(key.encode()).hexdigest(),
                role,
            )
        # Synthetic response history so the demo gate has a response rate to work with.
        await conn.execute(
            "INSERT INTO channel_stats (tenant_id, channel, asks, answers) "
            "VALUES ($1, 'web', 20, 16), ($1, 'agent', 20, 16)",
            tenant,
        )
    await conn.close()
    print(f"RESOLVEIT_API_KEY={keys['admin']}")
    print(f"RESOLVEIT_AGENT_KEY={keys['agent']}")


if __name__ == "__main__":
    asyncio.run(main())
