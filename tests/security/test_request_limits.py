"""Adversarial ASGI byte and concurrency checks independent of database fixtures."""

from __future__ import annotations

import asyncio

import pytest
from resolveit_api.request_limits import RequestLimits
from starlette.types import Message, Receive, Scope, Send


def scope(headers: list[tuple[bytes, bytes]] | None = None) -> Scope:
    return {"type": "http", "method": "POST", "path": "/mcp", "headers": headers or []}


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_actual_oversize_chunks_rejected_independent_of_length_header(
    headers: list[tuple[bytes, bytes]],
) -> None:
    async def run() -> None:
        called = False
        output: list[Message] = []
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 65536, "more_body": True},
                {"type": "http.request", "body": b"y" * 65537, "more_body": False},
            ]
        )

        async def receive() -> Message:
            return next(chunks)

        async def send(message: Message) -> None:
            output.append(message)

        async def downstream(current: Scope, incoming: Receive, outgoing: Send) -> None:
            nonlocal called
            called = True

        gate = RequestLimits(downstream)
        await gate(scope(headers), receive, send)
        assert not called
        assert output[0]["status"] == 413
        assert gate._active == 0

    asyncio.run(run())


def test_accepted_chunked_body_is_replayed_exactly_once() -> None:
    async def run() -> None:
        chunks = iter(
            [
                {"type": "http.request", "body": b"first-", "more_body": True},
                {"type": "http.request", "body": b"second", "more_body": False},
                {"type": "http.disconnect"},
            ]
        )

        async def receive() -> Message:
            return next(chunks)

        async def send(message: Message) -> None:
            raise AssertionError(f"Unexpected response: {message['type']}")

        async def downstream(current: Scope, incoming: Receive, outgoing: Send) -> None:
            first = await incoming()
            assert first["body"] == b"first-second" and not first["more_body"]
            assert (await incoming())["type"] == "http.disconnect"

        gate = RequestLimits(downstream)
        await gate(scope(), receive, send)
        assert gate._active == 0

    asyncio.run(run())


def test_concurrent_request_rejected_without_consuming_body_and_capacity_recovers() -> None:
    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        output: list[Message] = []
        received = 0

        async def receive() -> Message:
            nonlocal received
            received += 1
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            output.append(message)

        async def downstream(current: Scope, incoming: Receive, outgoing: Send) -> None:
            entered.set()
            await release.wait()

        gate = RequestLimits(downstream, max_concurrent=1)
        first = asyncio.create_task(gate(scope(), receive, send))
        await entered.wait()
        await gate(scope(), receive, send)
        assert output[0]["status"] == 429
        assert (b"retry-after", b"1") in output[0]["headers"]
        assert received == 1
        release.set()
        await first
        assert gate._active == 0
        await gate(scope(), receive, send)
        assert received == 2 and gate._active == 0

    asyncio.run(run())


def test_disconnect_releases_concurrency_capacity() -> None:
    async def run() -> None:
        called = False

        async def receive() -> Message:
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            raise AssertionError(f"Unexpected response: {message['type']}")

        async def downstream(current: Scope, incoming: Receive, outgoing: Send) -> None:
            nonlocal called
            called = True

        gate = RequestLimits(downstream)
        await gate(scope(), receive, send)
        assert not called and gate._active == 0

    asyncio.run(run())


def test_csv_admission_is_separate_and_released_after_cancellation() -> None:
    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        output: list[Message] = []
        reads = 0

        async def receive() -> Message:
            nonlocal reads
            reads += 1
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message: Message) -> None:
            output.append(message)

        async def downstream(current: Scope, incoming: Receive, outgoing: Send) -> None:
            if current["path"] == "/v1/bounce/analyze":
                entered.set()
                await release.wait()

        gate = RequestLimits(downstream, max_concurrent=32)
        csv_scope = scope()
        csv_scope["path"] = "/v1/bounce/analyze"
        first = asyncio.create_task(gate(csv_scope, receive, send))
        await entered.wait()
        await gate(csv_scope, receive, send)
        assert output[0]["status"] == 429 and reads == 1
        await gate(scope(), receive, send)
        assert reads == 2 and gate._csv_active == 1
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert gate._active == 0 and gate._csv_active == 0
        release.set()
        await gate(csv_scope, receive, send)
        assert reads == 3 and gate._csv_active == 0

    asyncio.run(run())
