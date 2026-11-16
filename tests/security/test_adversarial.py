from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from resolveit_api.auth import Principal, principal
from resolveit_api.routes import mcp
from resolveit_worker import runner


def test_signed_malformed_state_fails_closed() -> None:
    key, now = b"test-only-key", 1000.0
    who = Principal(uuid4(), "agent", "test-fingerprint")
    valid = {
        "i": str(uuid4()),
        "t": str(who.tenant_id),
        "r": who.role,
        "p": who.key_fingerprint,
        "d": "digest",
        "exp": now + 60,
    }
    for field, value in (
        ("exp", True),
        ("exp", "later"),
        ("exp", float("nan")),
        ("i", []),
        ("i", "bad"),
        ("p", "other-key"),
        ("d", "other-digest"),
    ):
        token = mcp.sign_state(key, {**valid, field: value})
        with pytest.raises(mcp.McpError):
            mcp.verify_state(key, token, who, "digest", now)


def test_state_cannot_cross_credentials_in_one_tenant() -> None:
    key, now = b"test-only-key", 1000.0
    who = Principal(uuid4(), "agent", "first-key")
    token = mcp.sign_state(
        key,
        {
            "i": str(uuid4()),
            "t": str(who.tenant_id),
            "r": who.role,
            "p": who.key_fingerprint,
            "d": "digest",
            "exp": now + 60,
        },
    )
    with pytest.raises(mcp.McpError, match="different principal"):
        mcp.verify_state(key, token, Principal(who.tenant_id, "agent", "second-key"), "digest", now)


def test_uncited_or_unrelated_agent_answers_stay_unknown() -> None:
    for content in ({"answer": "vpn"}, {"answer": "vpn", "evidence_quote": "printer"}):
        assert mcp._cited_answer({"action": "accept", "content": content}, "printer broken") == "unknown"


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"jsonrpc": "2.0", "id": True, "method": "ping"},
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []},
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"_meta": []}},
    ],
)
def test_malformed_rpc_returns_controlled_error(body: object) -> None:
    async def run() -> None:
        app = FastAPI()
        app.include_router(mcp.router)
        app.state.settings = SimpleNamespace(allowed_origins=("http://localhost:3000",))
        app.dependency_overrides[principal] = lambda: Principal(uuid4(), "agent", "test-key")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/mcp", json=body, headers={"MCP-Protocol-Version": mcp.STANDARD_VERSION}
            )
        assert response.status_code == 400
        assert "error" in response.json()

    asyncio.run(run())


def test_mcp_origin_denied_before_dispatch() -> None:
    async def run() -> None:
        app = FastAPI()
        app.include_router(mcp.router)
        app.state.settings = SimpleNamespace(allowed_origins=("http://localhost:3000",))
        app.dependency_overrides[principal] = lambda: Principal(uuid4(), "agent", "test-key")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Origin": "https://untrusted.invalid"},
            )
        assert response.status_code == 403

    asyncio.run(run())


def test_modern_discovery_matches_official_wire_schema() -> None:
    wire = pytest.importorskip("mcp_types._v2026_07_28")

    async def run() -> None:
        app = FastAPI()
        app.include_router(mcp.router)
        app.state.settings = SimpleNamespace(allowed_origins=())
        app.dependency_overrides[principal] = lambda: Principal(uuid4(), "agent", "test-key")
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "server/discover",
            "params": {"_meta": {mcp.META_VERSION: mcp.PROTOCOL_VERSION}},
        }
        headers = {"MCP-Protocol-Version": mcp.PROTOCOL_VERSION, "Mcp-Method": "server/discover"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/mcp", json=body, headers=headers)
        assert response.status_code == 200
        parsed = wire.DiscoverResult.model_validate(response.json()["result"])
        assert parsed.ttl_ms >= 0 and parsed.cache_scope in {"public", "private"}

    asyncio.run(run())


def test_worker_failure_log_contains_no_exception_payload(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    canary = "SYNTHETIC_PRIVATE_TICKET_CANARY"

    async def due(limit: int) -> list[tuple[object, object]]:
        return [(uuid4(), uuid4())]

    async def fail(*args: object) -> bool:
        raise ValueError(canary)

    monkeypatch.setattr(runner, "_has_open_question", fail)
    app = SimpleNamespace(db=SimpleNamespace(due_clarifications=due))
    with caplog.at_level(logging.ERROR, logger="resolveit.worker"):
        result = asyncio.run(runner.sweep(app))
    assert result.failed == 1
    leaked = canary in caplog.text
    assert not leaked, "Worker logged injected exception payload"
