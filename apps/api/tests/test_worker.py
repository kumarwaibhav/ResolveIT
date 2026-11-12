from __future__ import annotations

import asyncpg
import httpx
import pytest
from resolveit_worker.runner import LEADER_LOCK_ID, sweep

import resolveit_api.routes.intake as intake

from .conftest import TENANT_DEMO, auth

VAGUE = "it stopped working this morning, please help"


async def _expire(conn: asyncpg.Connection, incident_id: str) -> None:
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_DEMO))
        await conn.execute(
            "UPDATE incidents SET clarify_deadline = now() - interval '1 minute' WHERE id = $1", incident_id
        )


async def _fetch(conn: asyncpg.Connection, sql: str, *args: object) -> asyncpg.Record | None:
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_DEMO))
        return await conn.fetchrow(sql, *args)


async def test_unanswered_question_times_out_to_defer_without_counting_as_an_answer(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    out: dict = {}
    for _ in range(60):
        out = (await client.post("/v1/incidents", json={"text": VAGUE}, headers=auth("demo_admin"))).json()
        if out["question"]:
            break
    before = await _fetch(app_conn, "SELECT answers FROM channel_stats WHERE channel = 'web'")
    assert (await sweep(client.app.state)).timed_out == 0  # type: ignore[attr-defined]  # deadline not reached
    await _expire(app_conn, out["id"])
    result = await sweep(client.app.state)  # type: ignore[attr-defined]
    assert result.timed_out == 1 and result.failed == 0
    view = (await client.get(f"/v1/incidents/{out['id']}", headers=auth("demo_admin"))).json()
    assert view["state"] == "DEFERRED" and view["question"] is None
    q = await _fetch(app_conn, "SELECT outcome, answer FROM questions WHERE incident_id = $1", out["id"])
    after = await _fetch(app_conn, "SELECT answers FROM channel_stats WHERE channel = 'web'")
    assert q is not None and q["outcome"] == "timeout" and q["answer"] is None
    assert before is not None and after is not None and after["answers"] == before["answers"]
    assert (await sweep(client.app.state)).timed_out == 0  # type: ignore[attr-defined]  # idempotent


async def test_incident_survives_a_crash_between_persist_and_evaluate_and_is_recovered(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("simulated crash after persist")

    real = intake.evaluate
    monkeypatch.setattr(intake, "evaluate", boom)
    with pytest.raises(RuntimeError):
        await client.post(
            "/v1/incidents", json={"text": "VPN is down [crash-test]"}, headers=auth("demo_admin")
        )
    monkeypatch.setattr(intake, "evaluate", real)
    row = await _fetch(
        app_conn,
        "SELECT i.id, i.state FROM incidents i WHERE i.state = 'PENDING_CLARIFICATION' "
        "AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.incident_id = i.id) ORDER BY i.created_at DESC LIMIT 1",
    )
    assert row is not None, "the ticket must exist even though evaluation crashed"
    await _expire(app_conn, str(row["id"]))
    result = await sweep(client.app.state)  # type: ignore[attr-defined]
    assert result.recovered == 1 and result.failed == 0
    view = (await client.get(f"/v1/incidents/{row['id']}", headers=auth("demo_admin"))).json()
    assert view["state"] == "ROUTED" and view["routed_team"] == "Network"


async def test_only_one_worker_holds_the_leader_lock(client: httpx.AsyncClient) -> None:
    db = client.app.state.db  # type: ignore[attr-defined]
    async with db.leader_lock(LEADER_LOCK_ID) as first, db.leader_lock(LEADER_LOCK_ID) as second:
        assert first is True and second is False
    async with db.leader_lock(LEADER_LOCK_ID) as again:
        assert again is True


async def test_due_list_exposes_ids_only_and_app_role_cannot_read_incidents_directly(
    app_conn: asyncpg.Connection,
) -> None:
    cols = await app_conn.fetch("SELECT * FROM due_clarifications(5)")
    assert all(set(r.keys()) == {"tenant_id", "incident_id"} for r in cols)
    assert await app_conn.fetchval("SELECT count(*) FROM incidents") == 0
