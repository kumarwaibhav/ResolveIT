"""Runtime configuration from environment variables. No secrets have defaults."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_database_url: str
    master_key: bytes
    web_clarify_minutes: int = 10
    async_clarify_minutes: int = 240
    audit_rate: float = 0.05
    holdout_rate: float = 0.10
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")


def load_settings() -> Settings:
    try:
        url = os.environ["RESOLVEIT_APP_DATABASE_URL"]
        key = base64.b64decode(os.environ["RESOLVEIT_MASTER_KEY_B64"])
    except KeyError as exc:
        raise RuntimeError(f"missing required environment variable {exc.args[0]}") from exc
    if len(key) != 32:
        raise RuntimeError("RESOLVEIT_MASTER_KEY_B64 must decode to 32 bytes")
    origins = tuple(
        x.strip()
        for x in os.environ.get(
            "RESOLVEIT_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if x.strip()
    )
    return Settings(app_database_url=url, master_key=key, allowed_origins=origins)
