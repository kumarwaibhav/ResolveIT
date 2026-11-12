"""Stateless MCP endpoint, protocol revision 2026-07-28.

One tool, `submit_incident`. When the gate wants a clarification the server
returns an InputRequiredResult (resultType "input_required") carrying one
elicitation request and an HMAC-signed requestState. The client retries the
same tools/call with inputResponses and the echoed requestState; any server
instance can serve the retry.

requestState is attacker-controlled input. It is integrity-protected and
binds the tenant, the caller's role, an expiry and a digest of the original
arguments, as the specification requires. Single use is enforced by the
question row in Postgres, not by the token.

An agent's answer counts only if it quotes text that appears in the original
message; an uncited answer is recorded as "unknown".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from resolveit_core.schemas import UNKNOWN_ANSWER, Channel, EpistemicState
from resolveit_core.schemas.api import IncidentCreate, IncidentView
from resolveit_enterprise.privacy.crypto_shredder import SealedText, unseal
from sqlalchemy import text

from resolveit_api.auth import Principal, require_role
from resolveit_api.routes.intake import close_question, load_view, submit

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "resolveit", "version": "0.1.0"}
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"
META_SERVER = "io.modelcontextprotocol/serverInfo"
STATE_TTL_SECONDS = 15 * 60
INPUT_KEY = "clarify"

ERR_PARSE, ERR_INVALID_REQUEST, ERR_METHOD, ERR_PARAMS = -32700, -32600, -32601, -32602
ERR_HEADER_MISMATCH, ERR_UNSUPPORTED_VERSION = -32020, -32022
_TRACEPARENT = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")

router = APIRouter()
Caller = Annotated[Principal, Depends(require_role("agent", "admin"))]

TOOL = {
    "name": "submit_incident",
    "title": "Submit an IT incident",
    "description": (
        "Hand an IT problem report to ResolveIT. Returns the structured incident frame, the routing "
        "decision and a hand-off quality score. May ask one clarifying question first."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "minLength": 1,
                "maxLength": 20000,
                "description": "The user's report, verbatim. Do not summarise or rewrite it.",
            },
            "locale": {"type": "string", "enum": ["en", "hi", "hinglish"], "default": "en"},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}


class McpError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400) -> None:
        self.code, self.message, self.http_status = code, message, http_status


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def args_digest(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sign_state(key: bytes, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{_b64(body)}.{_b64(hmac.new(key, body, hashlib.sha256).digest())}"


def verify_state(key: bytes, token: str, who: Principal, digest: str, now: float) -> UUID:
    """Return the incident ID, or raise. Checks integrity, expiry, principal and originating arguments."""
    try:
        body_b64, mac_b64 = token.split(".")
        body = _unb64(body_b64)
        good = hmac.compare_digest(_unb64(mac_b64), hmac.new(key, body, hashlib.sha256).digest())
        payload = json.loads(body) if good else None
    except (ValueError, json.JSONDecodeError):
        payload = None
    if not isinstance(payload, dict):
        raise McpError(ERR_PARAMS, "requestState failed verification")
    if payload.get("exp", 0) < now:
        raise McpError(ERR_PARAMS, "requestState has expired; call the tool again without it")
    if payload.get("t") != str(who.tenant_id) or payload.get("r") != who.role:
        raise McpError(ERR_PARAMS, "requestState was issued to a different principal")
    if payload.get("d") != digest:
        raise McpError(ERR_PARAMS, "requestState does not belong to this request")
    return UUID(payload["i"])


def _result(req_id: Any, result: dict[str, Any], traceparent: str | None) -> JSONResponse:
    meta: dict[str, Any] = {META_SERVER: SERVER_INFO}
    if traceparent:
        meta["traceparent"] = traceparent
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {**result, "_meta": meta}})


def _error(req_id: Any, err: McpError) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": req_id, "error": {"code": err.code, "message": err.message}},
        status_code=err.http_status,
    )


def handoff_quality(view: IncidentView) -> float:
    """Share of the 11 frame slots that are PRESENT. A description of the hand-off, not a model score."""
    if not view.frame:
        return 0.0
    return round(sum(s.state is EpistemicState.PRESENT for s in view.frame) / len(view.frame), 3)


def _complete(view: IncidentView) -> dict[str, Any]:
    structured = {
        "incident": view.model_dump(mode="json"),
        "handoff_quality": handoff_quality(view),
        "missing_slots": [s.slot.value for s in view.frame if s.state is not EpistemicState.PRESENT],
    }
    d = view.decision
    summary = (
        f"Incident {view.id}: state {view.state}"
        + (f", routed to {view.routed_team}" if view.routed_team else "")
        + (
            f", recommended team {d.recommended_team.value} (not auto-routed)"
            if d and not view.routed_team and d.recommended_team
            else ""
        )
        + f". Hand-off quality {structured['handoff_quality']}."
    )
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": summary}],
        "structuredContent": structured,
        "isError": False,
    }


def _input_required(view: IncidentView, state: str) -> dict[str, Any]:
    q = view.question
    assert q is not None
    return {
        "resultType": "input_required",
        "inputRequests": {
            INPUT_KEY: {
                "method": "elicitation/create",
                "params": {
                    "mode": "form",
                    "message": q.text,
                    "requestedSchema": {
                        "type": "object",
                        "properties": {
                            "answer": {
                                "type": "string",
                                "enum": [o.value for o in q.options],
                                "description": f"Value for the '{q.slot.value}' slot. Use 'unknown' "
                                "if the user's message does not say.",
                            },
                            "evidence_quote": {
                                "type": "string",
                                "description": "Exact words from the "
                                "user's message that support the answer. Required unless "
                                "the answer is 'unknown'.",
                            },
                        },
                        "required": ["answer"],
                    },
                },
            }
        },
        "requestState": state,
    }


async def _raw_text(app: Any, tenant_id: UUID, incident_id: UUID) -> str | None:
    async with app.db.tenant_tx(tenant_id) as session:
        row = (
            await session.execute(
                text(
                    "SELECT x.raw_ciphertext, x.raw_nonce, k.wrapped_key FROM incident_text x "
                    "JOIN incident_keys k ON k.incident_id = x.incident_id WHERE x.incident_id = :i"
                ),
                {"i": incident_id},
            )
        ).first()
    if row is None or row[0] is None:
        return None
    return unseal(app.wrapper, tenant_id, incident_id, SealedText(row[2], row[1], row[0]))


def _cited_answer(response: Any, raw_text: str | None) -> str | None:
    """Map an ElicitResult to an answer. Decline or cancel is a skip; an uncited claim is 'unknown'."""
    if not isinstance(response, dict) or response.get("action") != "accept":
        return None
    content = response.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("answer"), str):
        return UNKNOWN_ANSWER
    answer = content["answer"]
    if answer == UNKNOWN_ANSWER:
        return UNKNOWN_ANSWER
    quote = content.get("evidence_quote")
    cited = (
        isinstance(quote, str)
        and len(quote.strip()) >= 2
        and raw_text is not None
        and quote.strip().casefold() in raw_text.casefold()
    )
    return answer if cited else UNKNOWN_ANSWER


async def _call_tool(app: Any, who: Principal, params: dict[str, Any]) -> dict[str, Any]:
    if params.get("name") != TOOL["name"]:
        raise McpError(ERR_PARAMS, f"unknown tool: {params.get('name')}")
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        raise McpError(ERR_PARAMS, "arguments must be an object")
    try:
        body = IncidentCreate(
            text=arguments.get("text", ""), locale=arguments.get("locale", "en"), channel=Channel.AGENT
        )
    except ValueError as exc:
        raise McpError(ERR_PARAMS, "invalid arguments for submit_incident") from exc
    if set(arguments) - {"text", "locale"}:
        raise McpError(ERR_PARAMS, "unexpected arguments for submit_incident")
    digest = args_digest(arguments)
    key: bytes = app.wrapper.index_key(who.tenant_id)
    caps = (params.get("_meta") or {}).get(META_CAPS) or {}
    can_elicit = isinstance(caps, dict) and "elicitation" in caps

    def state_for(incident_id: UUID) -> str:
        return sign_state(
            key,
            {
                "i": str(incident_id),
                "t": str(who.tenant_id),
                "r": who.role,
                "d": digest,
                "exp": int(time.time()) + STATE_TTL_SECONDS,
            },
        )

    token = params.get("requestState")
    if token is not None:
        if not isinstance(token, str):
            raise McpError(ERR_PARAMS, "requestState must be a string")
        incident_id = verify_state(key, token, who, digest, time.time())
        async with app.db.tenant_tx(who.tenant_id) as session:
            view = await load_view(app, session, who.tenant_id, incident_id)
        if view.question is None:
            return _complete(view)  # already closed: a replayed retry gets the stored outcome
        responses = params.get("inputResponses")
        if not isinstance(responses, dict) or INPUT_KEY not in responses:
            return _input_required(view, state_for(incident_id))  # ask again rather than fail
        answer = _cited_answer(responses[INPUT_KEY], await _raw_text(app, who.tenant_id, incident_id))
        return _complete(await close_question(app, who.tenant_id, who.role, incident_id, answer))

    idem = hashlib.sha256(f"{who.role}|{TOOL['name']}|{digest}".encode()).hexdigest()
    async with app.db.tenant_tx(who.tenant_id) as session:
        existing = (
            await session.execute(text("SELECT incident_id FROM mcp_calls WHERE idem_key = :k"), {"k": idem})
        ).scalar_one_or_none()
        current = await load_view(app, session, who.tenant_id, existing) if existing else None
    if current is None:
        current = await submit(app, who.tenant_id, body)
        async with app.db.tenant_tx(who.tenant_id) as session:
            await session.execute(
                text(
                    "INSERT INTO mcp_calls (tenant_id, idem_key, incident_id) VALUES (:t, :k, :i) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"t": who.tenant_id, "k": idem, "i": current.id},
            )
    if current.question is None:
        return _complete(current)
    if not can_elicit:
        # The client did not declare elicitation, so the server must not send one. Close as skipped.
        return _complete(await close_question(app, who.tenant_id, who.role, current.id, None))
    return _input_required(current, state_for(current.id))


@router.post("/mcp")
async def mcp(
    request: Request,
    who: Caller,
    mcp_protocol_version: Annotated[str | None, Header()] = None,
    mcp_method: Annotated[str | None, Header()] = None,
    mcp_name: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    req_id: Any = None
    try:
        try:
            msg = await request.json()
        except ValueError as exc:
            raise McpError(ERR_PARSE, "body is not valid JSON") from exc
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            raise McpError(ERR_INVALID_REQUEST, "not a JSON-RPC 2.0 request")
        req_id, method = msg.get("id"), msg["method"]
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            raise McpError(ERR_PARAMS, "params must be an object")
        meta = params.get("_meta") or {}
        if (
            mcp_protocol_version != PROTOCOL_VERSION
            or meta.get(META_VERSION, PROTOCOL_VERSION) != PROTOCOL_VERSION
        ):
            if mcp_protocol_version and meta.get(META_VERSION) and mcp_protocol_version != meta[META_VERSION]:
                raise McpError(ERR_HEADER_MISMATCH, "MCP-Protocol-Version header and _meta disagree")
            raise McpError(ERR_UNSUPPORTED_VERSION, f"supported protocol version: {PROTOCOL_VERSION}")
        if META_VERSION not in meta:
            raise McpError(ERR_INVALID_REQUEST, f"params._meta must carry {META_VERSION}")
        if mcp_method != method:
            raise McpError(ERR_HEADER_MISMATCH, "Mcp-Method header does not match the request method")
        if method == "tools/call" and mcp_name != params.get("name"):
            raise McpError(ERR_HEADER_MISMATCH, "Mcp-Name header does not match the tool name")
        tp = meta.get("traceparent")
        traceparent = tp if isinstance(tp, str) and _TRACEPARENT.match(tp) else None

        if method == "server/discover":
            return _result(
                req_id,
                {
                    "resultType": "complete",
                    "supportedVersions": [PROTOCOL_VERSION],
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
                traceparent,
            )
        if method == "tools/list":
            return _result(
                req_id,
                {"resultType": "complete", "tools": [TOOL], "ttlMs": 300_000, "cacheScope": "public"},
                traceparent,
            )
        if method == "tools/call":
            return _result(req_id, await _call_tool(request.app.state, who, params), traceparent)
        raise McpError(ERR_METHOD, f"method not supported: {method}", http_status=404)
    except McpError as err:
        return _error(req_id, err)


__all__ = ["PROTOCOL_VERSION", "router", "sign_state", "verify_state"]
