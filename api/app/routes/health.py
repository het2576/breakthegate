"""Liveness and warm-up (PRD 6.5, 13). Not behind the proxy secret.

/health/warm is for the Render cron: it needs the X-Warm-Secret header and is
disabled (404) when WARM_SECRET is unset. It sends one tiny decision to each
base model in use, uncached, so cold starts rarely reach players. The response
holds counts only, never model ids.
"""

import asyncio
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Header

from app.endor_client import LiveEndor
from app.http.errors import ApiError
from app.routes.deps import Ctx

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Makes no model or database calls."""
    return {"status": "ok"}


@router.get("/health/warm")
async def warm(
    ctx: Ctx, x_warm_secret: Annotated[str | None, Header(alias="X-Warm-Secret")] = None
) -> dict[str, Any]:
    expected = ctx.settings.warm_secret
    if expected is None:
        raise ApiError(404, "not_found", "Not found.")
    if not hmac.compare_digest((x_warm_secret or "").encode(), expected.encode()):
        raise ApiError(403, "forbidden", "Forbidden.")

    model_ids: set[str] = {ctx.config.resolve_verifier().model_id}
    for number, level in ctx.config.levels.items():
        if level.locked:
            continue
        for layer in ctx.config.resolve_level(number).layers:
            if layer.model_id is not None:
                model_ids.add(layer.model_id)

    client = ctx.inner_client
    if not isinstance(client, LiveEndor):
        return {"ok": True, "mode": "mock", "warmed": 0, "failed": 0}
    results = await asyncio.gather(*(client.warm(m) for m in model_ids), return_exceptions=True)
    failed = sum(isinstance(r, BaseException) for r in results)
    return {"ok": failed == 0, "mode": "live", "warmed": len(results) - failed, "failed": failed}
