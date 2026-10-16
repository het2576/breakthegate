"""Everything a request needs, built once at startup.

Decision calls go through: CachedEndor -> BreakerEndor -> Mock or Live client.
The cache sits in front, so repeats are free; the breaker guards real calls.
"""

from dataclasses import dataclass

from fastapi import Request

from app.breaker import BreakerEndor, CircuitBreaker
from app.budget import Budget
from app.cache import CachedEndor
from app.endor_client import LiveEndor, make_endor_client
from app.gate.config import GateConfig, load_config
from app.gate.types import EndorClient
from app.ratelimit import RateLimiter
from app.settings import Settings
from app.store import MemoryStore, Store
from app.turnstile import CloudflareVerifier, TurnstileVerifier, make_turnstile_verifier

HOUR_S = 3600.0


@dataclass
class AppContext:
    settings: Settings
    config: GateConfig
    store: Store
    inner_client: EndorClient  # uncached, unbroken: only /health/warm uses it directly
    client: EndorClient  # what the gate uses
    breaker: CircuitBreaker
    session_limiter: RateLimiter
    ip_limiter: RateLimiter
    budget: Budget
    turnstile: TurnstileVerifier


async def build_context(
    settings: Settings,
    *,
    config: GateConfig | None = None,
    store: Store | None = None,
    inner_client: EndorClient | None = None,
) -> AppContext:
    config = config or load_config()
    if store is None:
        if settings.database_url:
            from app.store.postgres import PostgresStore  # noqa: PLC0415 - optional at import

            store = await PostgresStore.connect(settings.database_url)
        else:
            store = MemoryStore()  # dev only; prod settings require DATABASE_URL
    inner = inner_client or make_endor_client(settings)
    breaker = CircuitBreaker()
    client = CachedEndor(BreakerEndor(inner, breaker), config.version)
    return AppContext(
        settings=settings,
        config=config,
        store=store,
        inner_client=inner,
        client=client,
        breaker=breaker,
        session_limiter=RateLimiter(settings.rate_session_per_hour, HOUR_S),
        ip_limiter=RateLimiter(settings.rate_ip_per_hour, HOUR_S),
        budget=Budget(
            store,
            config,
            max_usd=settings.max_daily_usd,
            max_tokens=settings.max_daily_tokens,
        ),
        turnstile=make_turnstile_verifier(settings.turnstile_secret),
    )


async def close_context(ctx: AppContext) -> None:
    await ctx.store.close()
    if isinstance(ctx.inner_client, LiveEndor):
        await ctx.inner_client.aclose()
    if isinstance(ctx.turnstile, CloudflareVerifier):
        await ctx.turnstile.aclose()


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx
