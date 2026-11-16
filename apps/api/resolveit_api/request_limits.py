"""Bound request bytes and concurrent work before authentication or JSON decoding.

Limits apply per API process. A production gateway must also enforce distributed
tenant quotas, connection limits and request deadlines across workers.
"""

from __future__ import annotations

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestLimits:
    def __init__(self, app: ASGIApp, max_concurrent: int = 32, max_csv_concurrent: int = 1) -> None:
        if max_concurrent < 1 or max_csv_concurrent < 1:
            raise ValueError("max_concurrent must be positive")
        self.app = app
        self.max_concurrent = max_concurrent
        self._active = 0
        # CSV requests can retain an 8MiB wire body plus decoded/parser objects.
        # Admit them separately so the 384MiB API does not accept 32 large bodies.
        self.max_csv_concurrent = max_csv_concurrent
        self._csv_active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_csv = scope.get("path") == "/v1/bounce/analyze"
        if self._active >= self.max_concurrent or (is_csv and self._csv_active >= self.max_csv_concurrent):
            await JSONResponse(
                {"detail": "server concurrency limit reached"}, status_code=429, headers={"Retry-After": "1"}
            )(scope, receive, send)
            return
        # No await between comparison and increment: atomic on the ASGI event loop.
        self._active += 1
        if is_csv:
            self._csv_active += 1
        try:
            limit = 8 * 1024 * 1024 if is_csv else 128 * 1024
            body = bytearray()
            deadline = asyncio.get_running_loop().time() + 10.0
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    if remaining <= 0:
                        raise TimeoutError
                    message = await asyncio.wait_for(receive(), timeout=remaining)
                except TimeoutError:
                    await JSONResponse({"detail": "request body deadline exceeded"}, status_code=408)(
                        scope, receive, send
                    )
                    return
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > limit:
                    await JSONResponse({"detail": "request body too large"}, status_code=413)(
                        scope, receive, send
                    )
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            consumed = False

            async def replay() -> Message:
                nonlocal consumed
                if consumed:
                    return await receive()
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, send)
        finally:
            self._active -= 1
            if is_csv:
                self._csv_active -= 1
