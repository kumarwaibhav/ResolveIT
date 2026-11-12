"""API-key authentication. The tenant comes from the verified key, never from the request body."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class Principal:
    tenant_id: UUID
    role: str


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def principal(request: Request, authorization: Annotated[str | None, Header()] = None) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    found = await request.app.state.db.resolve_api_key(hash_api_key(authorization[7:].strip()))
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid API key")
    return Principal(tenant_id=found[0], role=found[1])


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    async def check(p: Annotated[Principal, Depends(principal)]) -> Principal:
        if p.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "role not permitted")
        return p

    return check


__all__ = ["Principal", "hash_api_key", "principal", "require_role"]
