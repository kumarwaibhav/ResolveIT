"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from resolveit_enterprise.privacy.crypto_shredder import LocalKeyWrapper

from resolveit_api.bundles import shadow_bundle, synthetic_demo_bundle
from resolveit_api.db.session import Database
from resolveit_api.routes import intake, mcp
from resolveit_api.settings import Settings, load_settings
from resolveit_api.templates import TemplateBank


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.db.dispose()

    app = FastAPI(title="ResolveIT API", version="0.1.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.db = Database(cfg.app_database_url)
    app.state.wrapper = LocalKeyWrapper(cfg.master_key)
    # Keyed by tenants.is_synthetic: real tenants can only ever get the shadow bundle.
    app.state.bundles = {False: shadow_bundle(), True: synthetic_demo_bundle()}
    app.state.templates = TemplateBank()
    app.include_router(intake.router)
    app.include_router(mcp.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
