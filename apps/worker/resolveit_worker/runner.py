"""Background worker: closes clarifications that timed out and recovers unevaluated incidents.

Run with:  python -m resolveit_worker.runner
Connect it directly to Postgres, not through PgBouncer: the leader lock is a
session advisory lock.

Not here yet: the outbox drain and the audit-label queue. Those arrive with the
ITSM connector.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from resolveit_api.main import create_app
from resolveit_api.routes.intake import close_question, recover_unevaluated

LEADER_LOCK_ID = 7_301_001
log = logging.getLogger("resolveit.worker")


@dataclass(frozen=True, slots=True)
class SweepResult:
    timed_out: int
    recovered: int
    failed: int


async def _has_open_question(app: Any, tenant_id: Any, incident_id: Any) -> bool:
    async with app.db.tenant_tx(tenant_id) as session:
        row = (
            await session.execute(
                text("SELECT 1 FROM questions WHERE incident_id = :i AND outcome = 'pending'"),
                {"i": incident_id},
            )
        ).first()
    return row is not None


async def sweep(app: Any, limit: int = 100) -> SweepResult:
    """One pass over overdue incidents. Each incident is handled in its own tenant transaction."""
    timed_out = recovered = failed = 0
    for tenant_id, incident_id in await app.db.due_clarifications(limit):
        try:
            if await _has_open_question(app, tenant_id, incident_id):
                await close_question(app, tenant_id, "worker", incident_id, None, none_outcome="timeout")
                timed_out += 1
            elif await recover_unevaluated(app, tenant_id, incident_id):
                recovered += 1
        except Exception:
            failed += 1
            log.exception("sweep failed for incident %s", incident_id)  # IDs only, never ticket text
    return SweepResult(timed_out, recovered, failed)


async def run_forever(interval_seconds: float = 15.0) -> None:
    app = create_app().state
    while True:
        async with app.db.leader_lock(LEADER_LOCK_ID) as leader:
            if leader:
                result = await sweep(app)
                if result.timed_out or result.recovered or result.failed:
                    log.info("sweep: %s", result)
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
