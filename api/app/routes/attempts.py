"""POST /api/attempts and GET /api/attempts/me (docs/PRD.md 6.3, 6.6, 7).

Order inside POST (PRD 6.6): proxy secret, validate and moderate, idempotency
lookup, kill switch, breaker, rate limits, budget, gate engine and verifier,
insert, store the idempotent response. Cheap checks first, so a rejected request
costs nothing. Fail closed: no approval and no points unless the gate decided
and the verifier answered.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.breaker import BreakerOpen
from app.budget import utc_today
from app.context import AppContext
from app.endor_client import WarmingUp
from app.gate.engine import evaluate_attempt
from app.gate.scoring import score_attempt
from app.gate.types import GateDecision, GateState, LayerResult, VerifyResult
from app.goals import GOALS
from app.http.errors import ApiError
from app.http.security import client_ip
from app.moderation import SECRET_MESSAGE, looks_like_secret
from app.routes.deps import Ctx, CurrentSession
from app.store import AttemptRow, NewAttempt, SessionRow

logger = logging.getLogger("app.attempts")
router = APIRouter()

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
DEFAULT_RETRY_S = 10.0


class AttemptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: int = Field(ge=1, le=5)
    goal_id: int = Field(ge=1, le=12)
    task: str = Field(min_length=1, max_length=300)
    command: str = Field(min_length=1, max_length=1000)

    @field_validator("task", "command")
    @classmethod
    def _text(cls, value: str) -> str:
        # Text is passed to the gate exactly as typed; only reject what cannot be stored.
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        if "\x00" in value:
            raise ValueError("Remove the null character.")
        return value


def public_layer(layer: LayerResult) -> dict[str, Any]:
    """What the browser sees of a layer: no cache_hit, no token counts."""
    return {
        "name": layer.name,
        "passed": layer.passed,
        "p_safe": layer.p_safe,
        "detail": layer.detail,
    }


def _public_stored_layer(layer: dict[str, Any]) -> dict[str, Any]:
    return {k: layer.get(k) for k in ("name", "passed", "p_safe", "detail")}


def _request_hash(body: AttemptIn) -> str:
    canonical = json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_open(ctx: AppContext, level: int) -> None:
    if level not in ctx.config.levels:
        raise ApiError(422, "validation", "Unknown level.")
    if ctx.config.levels[level].locked:
        raise ApiError(422, "level_locked", "This level is locked.")


async def _guards(ctx: AppContext, session: SessionRow, ip: str | None) -> None:
    """Kill switch, breaker, rate limits, budget: all before any decision call."""
    if ctx.settings.game_paused:
        raise ApiError(503, "paused", "The game is paused. Check back soon.")
    if ctx.breaker.state == "open":
        raise ApiError(
            503, "breaker_open", "The gate is resting.", retry_after=ctx.breaker.retry_after()
        )

    session_key = f"s:{session.id}"
    ip_key = f"ip:{ip}" if ip else None
    waits = [ctx.session_limiter.retry_after(session_key)]
    if ip_key:
        waits.append(ctx.ip_limiter.retry_after(ip_key))
    wait = max((w for w in waits if w is not None), default=None)
    if wait is not None:
        seconds = int(-(-wait // 1))
        raise ApiError(
            429, "rate_limited", f"Too many attempts. Wait {seconds} seconds.", retry_after=wait
        )

    if await ctx.budget.exhausted(utc_today()):
        raise ApiError(503, "paused", "The game is paused. Check back soon.")

    ctx.session_limiter.record(session_key)
    if ip_key:
        ctx.ip_limiter.record(ip_key)


async def _decide(ctx: AppContext, body: AttemptIn) -> tuple[GateDecision, VerifyResult]:
    try:
        return await evaluate_attempt(
            body.level,
            GateState(task=body.task, command=body.command),
            GOALS[body.goal_id],
            ctx.config,
            ctx.client,
        )
    except WarmingUp as exc:
        raise ApiError(
            503,
            "warming_up",
            "The gate is waking up. The first attempt can take up to 3 minutes.",
            retry_after=exc.retry_after,
        ) from exc
    except BreakerOpen as exc:
        raise ApiError(
            503, "breaker_open", "The gate is resting.", retry_after=exc.retry_after
        ) from exc
    except Exception as exc:  # noqa: BLE001 - fail closed on anything else
        logger.warning("gate_unavailable error=%s", type(exc).__name__)
        raise ApiError(
            503,
            "gate_unavailable",
            "The gate could not decide. Try again shortly.",
            retry_after=DEFAULT_RETRY_S,
        ) from exc


async def _run_attempt(
    ctx: AppContext, body: AttemptIn, session: SessionRow, ip: str | None
) -> dict[str, Any]:
    await _guards(ctx, session, ip)
    started = time.perf_counter()
    gate, verify = await _decide(ctx, body)
    latency_ms = round((time.perf_counter() - started) * 1000)

    # The calls happened, so the spend counts even if we refuse to score below.
    await ctx.budget.record(utc_today(), body.level, gate, verify)

    if gate.approved and verify.verified is None:
        raise ApiError(
            503,
            "verifier_unavailable",
            "The goal check is resting. No points were given.",
            retry_after=verify.retry_after or DEFAULT_RETRY_S,
        )

    win = gate.approved and verify.verified is True
    repeat = win and await ctx.store.has_win_on_goal(session.id, body.level, body.goal_id)
    points = score_attempt(body.level, body.command, gate.approved, bool(verify.verified), repeat)

    row = await ctx.store.insert_attempt(
        NewAttempt(
            session_id=session.id,
            level=body.level,
            goal_id=body.goal_id,
            task=body.task,
            command=body.command,
            approved=gate.approved,
            p_safe=gate.p_safe,
            threshold=gate.threshold,
            deciding_layer=gate.deciding_layer,
            layers=[layer.model_dump() for layer in gate.layers],
            verified=verify.verified,
            verify_p=verify.verify_p,
            verify_cache_hit=verify.cache_hit,
            points=points,
            gate_version=gate.gate_version,
            latency_ms=latency_ms,
            consent_training=session.consent_training,
        )
    )
    logger.info(
        "attempt level=%d goal=%d approved=%s verified=%s deciding=%s points=%d latency_ms=%d "
        "cache_hits=%d gate_version=%s",
        body.level,
        body.goal_id,
        gate.approved,
        verify.verified,
        gate.deciding_layer,
        points,
        latency_ms,
        sum(layer.cache_hit for layer in gate.layers) + int(verify.cache_hit),
        gate.gate_version,
    )
    reveal_id: str | None = None
    if win:
        reveal = await ctx.store.create_reveal(
            attempt_id=row.id,
            session_id=session.id,
            level=body.level,
            variant="legendary" if body.level == 5 else "standard",
            needs_review=body.level == 5,
        )
        reveal_id = str(reveal.id) if reveal else None
    return {
        "attempt_id": str(row.id),
        "approved": gate.approved,
        "p_safe": gate.p_safe,
        "threshold": gate.threshold,
        "deciding_layer": gate.deciding_layer,
        "layers": [public_layer(layer) for layer in gate.layers],
        "verified": verify.verified,
        "points": points,
        "reveal_id": reveal_id,
        "gate_version": gate.gate_version,
    }


@router.post("/attempts")
async def submit_attempt(
    body: AttemptIn,
    request: Request,
    response: Response,
    session: CurrentSession,
    ctx: Ctx,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    _check_open(ctx, body.level)
    if looks_like_secret(body.task) or looks_like_secret(body.command):
        raise ApiError(422, "moderation", SECRET_MESSAGE)

    if idempotency_key is not None and not _IDEMPOTENCY_KEY.match(idempotency_key):
        raise ApiError(
            422, "validation", "Idempotency-Key must be 8 to 64 letters, digits, - or _."
        )

    ip = client_ip(request)
    if idempotency_key is None:
        return await _run_attempt(ctx, body, session, ip)

    claim = await ctx.store.claim_idempotency(session.id, idempotency_key, _request_hash(body))
    if claim.status == "replay" and claim.response is not None:
        response.headers["Idempotent-Replay"] = "true"
        return claim.response
    if claim.status == "reused":
        raise ApiError(
            422, "idempotency_key_reused", "This Idempotency-Key was used for a different attempt."
        )
    if claim.status == "in_progress":
        raise ApiError(
            409, "idempotency_in_progress", "This attempt is still running.", retry_after=1
        )

    try:
        result = await _run_attempt(ctx, body, session, ip)
    except BaseException:
        await ctx.store.release_idempotency(session.id, idempotency_key)
        raise
    await ctx.store.complete_idempotency(session.id, idempotency_key, result)
    return result


def _history_item(row: AttemptRow) -> dict[str, Any]:
    return {
        "attempt_id": str(row.id),
        "level": row.level,
        "goal_id": row.goal_id,
        "task": row.task,
        "command": row.command,
        "approved": row.approved,
        "p_safe": row.p_safe,
        "threshold": row.threshold,
        "deciding_layer": row.deciding_layer,
        "layers": [_public_stored_layer(layer) for layer in row.layers],
        "verified": row.verified,
        "points": row.points,
        "gate_version": row.gate_version,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/attempts/me")
async def my_attempts(
    session: CurrentSession,
    ctx: Ctx,
    level: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    before: Annotated[datetime | None, Query()] = None,
) -> dict[str, Any]:
    rows = await ctx.store.list_attempts(session.id, level=level, limit=limit, before=before)
    next_before = rows[-1].created_at.isoformat() if len(rows) == limit else None
    return {"attempts": [_history_item(r) for r in rows], "next_before": next_before}
