"""Break the Gate API entrypoint: `uvicorn app.main:app`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.context import build_context, close_context
from app.gate.config import GateConfig
from app.gate.types import EndorClient
from app.http.errors import install_error_handlers
from app.routes import attempts, health, public, sessions
from app.routes.deps import require_proxy
from app.settings import Settings
from app.store import Store


def create_app(
    settings: Settings | None = None,
    *,
    config: GateConfig | None = None,
    store: Store | None = None,
    inner_client: EndorClient | None = None,
) -> FastAPI:
    """Build the app. Tests inject a store and a decision client; production reads env."""
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # A bad gates.yaml or missing secret fails here, before serving anything.
        ctx = await build_context(resolved, config=config, store=store, inner_client=inner_client)
        app.state.ctx = ctx
        try:
            yield
        finally:
            await close_context(ctx)

    prod = resolved.app_env == "prod"
    app = FastAPI(
        title="Break the Gate API",
        lifespan=lifespan,
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )
    install_error_handlers(app)

    api = APIRouter(prefix="/api", dependencies=[Depends(require_proxy)])
    api.include_router(public.router)
    api.include_router(sessions.router)
    api.include_router(attempts.router)
    app.include_router(health.router)
    app.include_router(api)
    return app


app = create_app()
