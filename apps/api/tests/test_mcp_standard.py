from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import httpx
import pytest

from resolveit_api.auth import Principal
from resolveit_api.routes.mcp import McpError, sign_state, verify_state

from .conftest import TENANT_A, auth


async def test_standard_initialization_list_call_notification(client: httpx.AsyncClient) -> None:
    headers = {**auth("demo_agent"), "Accept": "application/json, text/event-stream"}
    response = await client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "standard-test", "version": "1"},
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"
    headers["MCP-Protocol-Version"] = "2025-11-25"
    notification = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert notification.status_code == 202 and not notification.content
    listed = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    )
    assert listed.json()["result"]["tools"][0]["name"] == "submit_incident"
    called = await client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "submit_incident", "arguments": {"text": "VPN down [standard-client]"}},
        },
    )
    result = called.json()["result"]
    assert not result["isError"] and "content" in result and "resultType" not in result


async def test_mcp_origin_and_metadata_shapes(client: httpx.AsyncClient) -> None:
    for origin in ("https://attacker.example", "null"):
        response = await client.post(
            "/mcp",
            headers={**auth("demo_agent"), "Origin": origin},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            },
        )
        assert response.status_code == 403
    for params in ([], {"_meta": []}, {"_meta": "bad"}):
        response = await client.post(
            "/mcp",
            headers=auth("demo_agent"),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params},
        )
        assert response.status_code == 400 and response.json()["error"]["code"] == -32602
    assert (await client.get("/mcp", headers=auth("demo_agent"))).status_code == 405


async def test_concurrent_mcp_deduplication(client: httpx.AsyncClient) -> None:
    async def call(n: int) -> str:
        response = await client.post(
            "/mcp",
            headers={**auth("demo_agent"), "MCP-Protocol-Version": "2025-11-25"},
            json={
                "jsonrpc": "2.0",
                "id": n,
                "method": "tools/call",
                "params": {
                    "name": "submit_incident",
                    "arguments": {"text": "VPN down [concurrent-standard]"},
                    "_meta": {"resolveit/idempotencyKey": "concurrent-standard-test"},
                },
            },
        )
        return str(response.json()["result"]["structuredContent"]["incident"]["id"])

    assert len(set(await asyncio.gather(*(call(i) for i in range(12))))) == 1


async def test_agent_cannot_bypass_citations_using_rest(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"/v1/incidents/{uuid4()}/answer", headers=auth("demo_agent"), json={"answer": "vpn"}
    )
    assert response.status_code == 403


def test_state_invalid_fields_are_protocol_errors() -> None:
    key = b"k" * 32
    who = Principal(TENANT_A, "agent", "fingerprint")
    payload = {
        "t": str(TENANT_A),
        "r": "agent",
        "p": "fingerprint",
        "d": "digest",
        "exp": time.time() + 60,
        "i": str(uuid4()),
    }
    for change in ({"exp": "forever"}, {"exp": float("nan")}, {"i": "invalid"}, {"p": "another-key"}):
        with pytest.raises(McpError):
            verify_state(key, sign_state(key, {**payload, **change}), who, "digest", time.time())
