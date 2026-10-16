"""Public game data and session-bound reveal claims (PRD 7)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query

from app.http.errors import ApiError
from app.levels import public_levels
from app.report_file import published_report
from app.routes.deps import Ctx, CurrentSession

router = APIRouter()

LEADERBOARD_SIZE = 50


@router.get("/levels")
async def levels(ctx: Ctx) -> dict[str, Any]:
    return public_levels(ctx.config, await ctx.store.level_progress())


@router.get("/leaderboard")
async def leaderboard(ctx: Ctx, level: Annotated[int, Query(ge=1, le=5)]) -> dict[str, Any]:
    rows = await ctx.store.leaderboard(level, LEADERBOARD_SIZE)
    return {
        "level": level,
        "entries": [
            {"rank": i, "handle": r.handle, "score": r.score, "attempts": r.attempts}
            for i, r in enumerate(rows, start=1)
        ],
    }


@router.get("/report")
async def report(ctx: Ctx) -> dict[str, Any]:
    # Every number on the report page comes from a stored eval file (PRD 1.5).
    return {"report": await ctx.store.latest_eval() or published_report()}


def _public_win(win: Any) -> dict[str, Any]:
    return {
        "variant": win.variant,
        "level": win.level,
        "attempts": win.attempts,
        "seconds": win.seconds,
        "badge": f"Gate breaker, level {win.level}",
    }


@router.post("/reveals/{reveal_id}/claim")
async def claim_reveal(reveal_id: str, session: CurrentSession, ctx: Ctx) -> dict[str, Any]:
    try:
        parsed_id = UUID(reveal_id)
    except ValueError as exc:
        raise ApiError(404, "not_found", "Reveal not found.") from exc
    claim = await ctx.store.claim_reveal(session.id, parsed_id)
    if claim.status == "not_found":
        raise ApiError(404, "not_found", "Reveal not found.")
    if claim.status == "already_claimed":
        raise ApiError(409, "already_claimed", "This reveal was already claimed.")
    if claim.status == "expired":
        raise ApiError(410, "reveal_expired", "This reveal expired. Your win and badge are saved.")
    assert claim.win is not None  # noqa: S101 - claimed responses always carry the win summary
    return {**_public_win(claim.win), "video_id": ctx.settings.reveal_video_id}


@router.get("/wins/me")
async def wins(session: CurrentSession, ctx: Ctx) -> dict[str, Any]:
    return {
        "wins": [
            {**_public_win(win), "claimed": win.claimed}
            for win in await ctx.store.list_wins(session.id)
        ]
    }
