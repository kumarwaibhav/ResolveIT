"""Independent local synthetic SDK smoke; credentials stay in environment.

Run with RESOLVEIT_API_URL=http://127.0.0.1:8000 and RESOLVEIT_API_KEY set.
Requires official mcp>=2.3 and httpx2. Performs a real synthetic incident write.
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlsplit


async def sdk_smoke() -> None:
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    base = os.environ.get("RESOLVEIT_API_URL", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlsplit(base)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password:
        raise ValueError("SDK gate permits loopback targets without URL credentials only")
    key = os.environ["RESOLVEIT_API_KEY"]
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=20) as client:
        # Verify provenance before writing; an admin credential is required.
        evaluation = await client.get(f"{base}/v1/evaluation")
        evaluation.raise_for_status()
        if evaluation.json().get("provenance") != "synthetic_seed":
            raise ValueError("SDK write gate requires synthetic tenant")
        async with (
            streamable_http_client(f"{base}/mcp", http_client=client) as streams,
            ClientSession(*streams, read_timeout_seconds=20) as session,
        ):
            initialized = await session.initialize()
            if initialized.protocol_version != "2025-11-25":
                raise ValueError("Unexpected negotiated legacy protocol")
            listing = await session.list_tools()
            if "submit_incident" not in {tool.name for tool in listing.tools}:
                raise ValueError("Incident tool missing")
            result = await session.call_tool(
                "submit_incident", {"text": "VPN down [official SDK synthetic smoke]", "locale": "en"}
            )
            if result.is_error:
                raise ValueError("SDK tool call returned isError")
            structured = result.structured_content or {}
            incident = structured.get("incident", {})
            if not incident.get("is_synthetic_tenant"):
                raise ValueError("Tool did not return synthetic provenance")
            print("Official MCP SDK initialize/list/call passed; synthetic incident persisted.")


def main() -> int:
    try:
        asyncio.run(sdk_smoke())
    except Exception as exc:
        # Exception messages can include HTTP headers/response ticket text.
        print(f"SDK gate failed: {type(exc).__name__}; details withheld.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
