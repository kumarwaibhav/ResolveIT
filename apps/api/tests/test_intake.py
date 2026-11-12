from __future__ import annotations

import asyncpg
import httpx

from .conftest import auth

AMBIGUOUS_TEXT = "it stopped working this morning, please help"


async def _post(client: httpx.AsyncClient, key: str, body: str, **extra: str) -> dict:
    r = await client.post("/v1/incidents", json={"text": body, **extra}, headers=auth(key))
    assert r.status_code == 201, r.text
    return r.json()


async def _row(conn: asyncpg.Connection, tenant: str, sql: str, *args: object) -> asyncpg.Record | None:
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", tenant)
        return await conn.fetchrow(sql, *args)


async def _tenant_of(conn: asyncpg.Connection, key_hash_role: str) -> str:
    from resolveit_api.auth import hash_api_key

    row = await conn.fetchrow("SELECT tenant_id FROM resolve_api_key($1)", hash_api_key(key_hash_role))
    return str(row["tenant_id"])


async def test_real_tenant_is_shadow_mode_and_never_auto_routes(client: httpx.AsyncClient) -> None:
    out = await _post(client, "a_admin", "VPN is down for the whole floor, urgent")
    assert out["state"] == "DEFERRED" and out["routed_team"] is None
    d = out["decision"]
    assert d["action"] == "DEFER" and d["defer_reason"] == "shadow_mode" and d["tau_hat"] is None
    assert d["recommended_team"] == "Network" and d["bundle_id"].startswith("rules-shadow-uncalibrated-")
    assert out["is_synthetic_tenant"] is False and out["question"] is None


async def test_demo_tenant_routes_a_clear_ticket_with_faithful_evidence(client: httpx.AsyncClient) -> None:
    text = "😀 VPN is down again for the whole floor"
    out = await _post(client, "demo_admin", text)
    d = out["decision"]
    assert out["is_synthetic_tenant"] is True and d["bundle_id"].startswith("synthetic-demo-")
    assert d["action"] == "ROUTE" and d["team"] == "Network" and out["state"] == "ROUTED"
    assert (
        "Network" in d["conformal"]["teams"]
        and len(d["conformal"]["teams"]) <= 3
        and d["tau_hat"] is not None
    )
    top = d["attributions"][0]
    assert top["slot"] == "service" and top["value"] == "vpn" and top["delta_p"] > 0.5
    service = next(s for s in out["frame"] if s["slot"] == "service")
    span = service["evidence"][0]
    utf16 = text.encode("utf-16-le")
    assert utf16[span["start"] * 2 : span["end"] * 2].decode("utf-16-le") == "VPN"  # as a browser slices it
    assert span["start"] == 3  # the emoji is two UTF-16 units; code-point offset would be 2


async def test_persist_first_encrypted_at_rest_and_masked(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    out = await _post(client, "demo_admin", "Outlook crash, call me on 9876543210, error 0x80070005")
    tenant = await _tenant_of(app_conn, "demo_admin")
    inc = await _row(
        app_conn,
        tenant,
        "SELECT sla_started_at, clarify_deadline, state FROM incidents WHERE id = $1",
        out["id"],
    )
    assert inc is not None and inc["sla_started_at"] is not None
    txt = await _row(
        app_conn,
        tenant,
        "SELECT masked_text, raw_ciphertext FROM incident_text WHERE incident_id = $1",
        out["id"],
    )
    assert txt is not None
    assert "9876543210" not in txt["masked_text"] and "<PHONE_IN>" in txt["masked_text"]
    assert "0x80070005" in txt["masked_text"]
    assert b"9876543210" not in txt["raw_ciphertext"] and b"Outlook" not in txt["raw_ciphertext"]
    stored = await _row(
        app_conn, tenant, "SELECT count(*) AS n FROM subject_index WHERE incident_id = $1", out["id"]
    )
    assert stored is not None and stored["n"] == 1


async def _ask(client: httpx.AsyncClient, key: str = "demo_admin", **extra: str) -> dict:
    """Submit until the ticket is not in the 10% no-ask holdout."""
    for _ in range(60):
        out = await _post(client, key, AMBIGUOUS_TEXT, **extra)
        if not out["decision"]["no_ask_holdout"]:
            return out
    raise AssertionError("always in holdout")


async def test_vague_ticket_exists_before_the_question_and_gets_exactly_one(
    client: httpx.AsyncClient,
) -> None:
    out = await _ask(client, locale="hinglish")
    assert out["state"] == "PENDING_CLARIFICATION" and out["decision"]["action"] == "ASK"
    q = out["question"]
    assert q["slot"] == "service" and q["skip_allowed"] is True
    assert q["text"] == "Yeh problem kis system ya app mein hai?"
    assert q["options"][-1] == {"value": "unknown", "label": "Pata nahi"}
    again = await client.get(f"/v1/incidents/{out['id']}", headers=auth("demo_admin"))
    assert again.json()["question"]["slot"] == "service"

    r = await client.post(
        f"/v1/incidents/{out['id']}/answer", json={"answer": "vpn"}, headers=auth("demo_admin")
    )
    done = r.json()
    assert r.status_code == 200 and done["state"] == "ROUTED" and done["routed_team"] == "Network"
    assert done["question"] is None and done["decision"]["action"] == "ROUTE"
    assert next(s for s in done["frame"] if s["slot"] == "service")["value"] == "vpn"
    r2 = await client.post(
        f"/v1/incidents/{out['id']}/answer", json={"answer": "email"}, headers=auth("demo_admin")
    )
    assert r2.status_code == 409  # one question, one answer


async def test_skip_and_unknown_defer_without_blocking(client: httpx.AsyncClient) -> None:
    for answer in (None, "unknown", "not an option"):
        out = await _ask(client)
        r = await client.post(
            f"/v1/incidents/{out['id']}/answer", json={"answer": answer}, headers=auth("demo_admin")
        )
        done = r.json()
        assert done["state"] == "DEFERRED" and done["decision"]["action"] == "DEFER"
        assert done["question"] is None


async def test_response_rate_is_tracked_per_channel(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    tenant = await _tenant_of(app_conn, "demo_admin")
    before = await _row(app_conn, tenant, "SELECT asks, answers FROM channel_stats WHERE channel = 'web'")
    assert before is not None
    out = await _ask(client)
    await client.post(
        f"/v1/incidents/{out['id']}/answer", json={"answer": "email"}, headers=auth("demo_admin")
    )
    skipped = await _ask(client)
    await client.post(
        f"/v1/incidents/{skipped['id']}/answer", json={"answer": None}, headers=auth("demo_admin")
    )
    after = await _row(app_conn, tenant, "SELECT asks, answers FROM channel_stats WHERE channel = 'web'")
    assert after is not None
    assert after["asks"] - before["asks"] == 2 and after["answers"] - before["answers"] == 1


async def test_holdout_tickets_are_never_asked(client: httpx.AsyncClient) -> None:
    seen_holdout = False
    for _ in range(120):
        out = await _post(client, "demo_admin", AMBIGUOUS_TEXT)
        if out["decision"]["no_ask_holdout"]:
            seen_holdout = True
            assert out["question"] is None and out["state"] == "DEFERRED"
            break
    assert seen_holdout


async def test_security_trigger_is_flagged_and_recommended_to_security(client: httpx.AsyncClient) -> None:
    out = await _post(client, "demo_admin", "I clicked on a link in a suspicious email, account got hacked")
    assert out["security_trigger"] is True
    assert out["decision"]["recommended_team"] == "Security"


async def test_agent_answer_is_recorded_as_agent_asserted(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    out = await _ask(client, key="demo_agent", channel="agent")
    await client.post(
        f"/v1/incidents/{out['id']}/answer", json={"answer": "wifi"}, headers=auth("demo_agent")
    )
    tenant = await _tenant_of(app_conn, "demo_agent")
    q = await _row(
        app_conn, tenant, "SELECT outcome, answer_source FROM questions WHERE incident_id = $1", out["id"]
    )
    assert q is not None and q["outcome"] == "answered" and q["answer_source"] == "agent_asserted"


async def test_erasure_crypto_shreds_every_incident_of_the_subject(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    a = await _post(client, "demo_admin", "laptop dead, reach me at priya.k@corp.in")
    b = await _post(client, "demo_admin", "printer broken - Priya.K@Corp.in")
    other = await _post(client, "demo_admin", "printer broken, mail someone.else@corp.in")
    r = await client.post(
        "/v1/privacy/erasure",
        json={"kind": "EMAIL", "identifier": " PRIYA.K@corp.in "},
        headers=auth("demo_admin"),
    )
    assert r.status_code == 200 and r.json() == {"incidents_erased": 2}
    tenant = await _tenant_of(app_conn, "demo_admin")
    for inc in (a, b):
        view = (await client.get(f"/v1/incidents/{inc['id']}", headers=auth("demo_admin"))).json()
        assert view["state"] == "ERASED" and view["frame"] == [] and view["decision"] is None
        key = await _row(app_conn, tenant, "SELECT 1 FROM incident_keys WHERE incident_id = $1", inc["id"])
        txt = await _row(
            app_conn,
            tenant,
            "SELECT masked_text, raw_ciphertext, tombstoned_at FROM incident_text WHERE incident_id = $1",
            inc["id"],
        )
        assert key is None and txt is not None
        assert (
            txt["masked_text"] is None and txt["raw_ciphertext"] is None and txt["tombstoned_at"] is not None
        )
    kept = (await client.get(f"/v1/incidents/{other['id']}", headers=auth("demo_admin"))).json()
    assert kept["state"] != "ERASED" and kept["frame"]
    again = await client.post(
        "/v1/privacy/erasure",
        json={"kind": "EMAIL", "identifier": "priya.k@corp.in"},
        headers=auth("demo_admin"),
    )
    assert again.json() == {"incidents_erased": 0}
