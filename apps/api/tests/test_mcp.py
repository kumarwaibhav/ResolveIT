from __future__ import annotations

import time
from typing import Any

import asyncpg
import httpx

from resolveit_api.auth import Principal
from resolveit_api.routes.mcp import args_digest, sign_state

from .conftest import TENANT_A, TENANT_DEMO, auth

V = "2026-07-28"
VAGUE = "it stopped working this morning, please help"


def headers(key: str, method: str, name: str | None = None, version: str = V) -> dict[str, str]:
    h = {**auth(key), "MCP-Protocol-Version": version, "Mcp-Method": method}
    if name:
        h["Mcp-Name"] = name
    return h


def call(args: dict[str, Any], rid: int = 1, elicit: bool = True, **extra: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "io.modelcontextprotocol/protocolVersion": V,
        "io.modelcontextprotocol/clientInfo": {"name": "test-agent", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}} if elicit else {},
    }
    meta.update(extra.pop("meta", {}))
    return {
        "jsonrpc": "2.0",
        "id": rid,
        "method": "tools/call",
        "params": {"name": "submit_incident", "arguments": args, "_meta": meta, **extra},
    }


async def post(client: httpx.AsyncClient, body: dict[str, Any], key: str = "demo_agent") -> httpx.Response:
    name = body.get("params", {}).get("name")
    return await client.post("/mcp", json=body, headers=headers(key, body["method"], name))


async def ask(client: httpx.AsyncClient, tag: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (arguments, input_required result) for a ticket outside the no-ask holdout."""
    for i in range(80):
        args = {"text": f"{VAGUE} [{tag}-{i}]"}
        res = (await post(client, call(args))).json()["result"]
        if res["resultType"] == "input_required":
            return args, res
    raise AssertionError("never asked")


async def test_discover_and_list(client: httpx.AsyncClient) -> None:
    meta = {"_meta": {"io.modelcontextprotocol/protocolVersion": V}}
    d = (await post(client, {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": meta})).json()
    assert d["result"]["supportedVersions"] == [V] and d["result"]["resultType"] == "complete"
    assert d["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "resolveit"
    t = (await post(client, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": meta})).json()[
        "result"
    ]
    assert (
        [x["name"] for x in t["tools"]] == ["submit_incident"]
        and t["ttlMs"] > 0
        and t["cacheScope"] == "public"
    )


async def test_header_and_version_enforcement(client: httpx.AsyncClient) -> None:
    body = call({"text": "VPN down"})
    r = await client.post(
        "/mcp", json=body, headers=headers("demo_agent", "tools/call", "submit_incident", "2025-11-25")
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == -32020  # header and _meta disagree
    old = call({"text": "VPN down"}, meta={"io.modelcontextprotocol/protocolVersion": "2025-11-25"})
    r = await client.post(
        "/mcp", json=old, headers=headers("demo_agent", "tools/call", "submit_incident", "2025-11-25")
    )
    assert r.json()["error"]["code"] == -32022
    r = await client.post("/mcp", json=body, headers=headers("demo_agent", "tools/list", "submit_incident"))
    assert r.json()["error"]["code"] == -32020
    r = await client.post("/mcp", json=body, headers=headers("demo_agent", "tools/call", "other_tool"))
    assert r.json()["error"]["code"] == -32020
    r = await client.post("/mcp", json=body, headers=headers("demo_agent", "tools/call"))
    assert r.json()["error"]["code"] == -32020
    assert (await client.post("/mcp", json=body, headers={"MCP-Protocol-Version": V})).status_code == 401
    assert (await post(client, body, key="a_viewer")).status_code == 403


async def test_clear_ticket_completes_in_one_round_trip_with_trace_echo(client: httpx.AsyncClient) -> None:
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    res = (
        await post(client, call({"text": "VPN is down again for the whole floor"}, meta={"traceparent": tp}))
    ).json()["result"]
    assert res["resultType"] == "complete" and res["isError"] is False
    sc = res["structuredContent"]
    assert sc["incident"]["state"] == "ROUTED" and sc["incident"]["routed_team"] == "Network"
    assert 0 < sc["handoff_quality"] < 1 and "symptom" in sc["missing_slots"]
    assert res["_meta"]["traceparent"] == tp
    bad = (await post(client, call({"text": "wifi slow in office"}, meta={"traceparent": "garbage"}))).json()[
        "result"
    ]
    assert "traceparent" not in bad["_meta"]


async def test_duplicate_call_creates_one_incident(
    client: httpx.AsyncClient, app_conn: asyncpg.Connection
) -> None:
    args = {"text": "printer on floor 3 is jammed [dedupe]"}
    ids = {
        (await post(client, call(args, rid=i))).json()["result"]["structuredContent"]["incident"]["id"]
        for i in range(3)
    }
    assert len(ids) == 1
    async with app_conn.transaction():
        await app_conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(TENANT_DEMO))
        assert (
            await app_conn.fetchval("SELECT count(*) FROM mcp_calls WHERE incident_id = $1", next(iter(ids)))
            == 1
        )


async def test_two_round_trips_with_cited_answer_routes(client: httpx.AsyncClient) -> None:
    for i in range(80):
        args = {"text": f"my vpn client says nothing, {VAGUE} [cited-{i}]".replace("vpn", "v-p-n")}
        res = (await post(client, call(args))).json()["result"]
        if res["resultType"] == "input_required":
            break
    req = res["inputRequests"]["clarify"]
    assert req["method"] == "elicitation/create" and req["params"]["mode"] == "form"
    assert "unknown" in req["params"]["requestedSchema"]["properties"]["answer"]["enum"]
    assert isinstance(res["requestState"], str)
    retry = call(
        args,
        rid=2,
        requestState=res["requestState"],
        inputResponses={
            "clarify": {"action": "accept", "content": {"answer": "vpn", "evidence_quote": "v-p-n client"}}
        },
    )
    done = (await post(client, retry)).json()["result"]
    assert done["resultType"] == "complete"
    assert done["structuredContent"]["incident"]["routed_team"] == "Network"
    replay = (await post(client, retry)).json()[
        "result"
    ]  # same retry again: stored outcome, no second answer
    assert replay["structuredContent"]["incident"]["id"] == done["structuredContent"]["incident"]["id"]
    assert replay["structuredContent"]["incident"]["state"] == "ROUTED"


async def test_uncited_or_invented_answer_counts_as_unknown(client: httpx.AsyncClient) -> None:
    for content in (
        {"answer": "vpn"},
        {"answer": "vpn", "evidence_quote": "the VPN gateway in Mumbai is down"},
    ):
        args, res = await ask(client, f"uncited-{len(content)}")
        retry = call(
            args,
            rid=2,
            requestState=res["requestState"],
            inputResponses={"clarify": {"action": "accept", "content": content}},
        )
        inc = (await post(client, retry)).json()["result"]["structuredContent"]["incident"]
        assert inc["state"] == "DEFERRED" and inc["routed_team"] is None
        assert next(s for s in inc["frame"] if s["slot"] == "service")["state"] == "MISSING"


async def test_decline_is_a_skip_and_missing_response_asks_again(client: httpx.AsyncClient) -> None:
    args, res = await ask(client, "decline")
    again = (await post(client, call(args, rid=2, requestState=res["requestState"]))).json()["result"]
    assert again["resultType"] == "input_required"
    retry = call(
        args, rid=3, requestState=again["requestState"], inputResponses={"clarify": {"action": "decline"}}
    )
    inc = (await post(client, retry)).json()["result"]["structuredContent"]["incident"]
    assert inc["state"] == "DEFERRED"


async def test_client_without_elicitation_is_never_asked(client: httpx.AsyncClient) -> None:
    res = (await post(client, call({"text": f"{VAGUE} [no-elicit]"}, elicit=False))).json()["result"]
    assert res["resultType"] == "complete" and res["structuredContent"]["incident"]["state"] == "DEFERRED"


async def test_request_state_tampering_expiry_and_cross_use_are_rejected(client: httpx.AsyncClient) -> None:
    args, res = await ask(client, "tamper")
    state = res["requestState"]
    answer = {"clarify": {"action": "accept", "content": {"answer": "unknown"}}}

    async def code(token: str, arguments: dict[str, Any] = args, key: str = "demo_agent") -> int:
        r = await post(client, call(arguments, rid=9, requestState=token, inputResponses=answer), key=key)
        return r.json()["error"]["code"]

    body, mac = state.split(".")
    assert await code(body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + mac) == -32602
    assert await code(body + "." + mac[::-1]) == -32602
    assert await code("not-a-token") == -32602
    assert await code(state, arguments={"text": "a different request"}) == -32602
    assert await code(state, key="demo_admin") == -32602  # same tenant, different principal role
    signing_key = client.app.state.wrapper.index_key(TENANT_DEMO)  # type: ignore[attr-defined]
    who = Principal(TENANT_DEMO, "agent")
    incident = res_incident_id(state)
    expired = sign_state(
        signing_key,
        {
            "i": incident,
            "t": str(who.tenant_id),
            "r": who.role,
            "d": args_digest(args),
            "exp": int(time.time()) - 1,
        },
    )
    assert await code(expired) == -32602
    foreign = sign_state(
        client.app.state.wrapper.index_key(TENANT_A),  # type: ignore[attr-defined]
        {
            "i": incident,
            "t": str(TENANT_A),
            "r": "agent",
            "d": args_digest(args),
            "exp": int(time.time()) + 600,
        },
    )
    assert await code(foreign) == -32602
    ok = await post(client, call(args, rid=10, requestState=state, inputResponses=answer))
    assert ok.json()["result"]["resultType"] == "complete"  # the untouched token still works


def res_incident_id(state: str) -> str:
    import base64
    import json

    body = state.split(".")[0]
    return str(json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))["i"])
