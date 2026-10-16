"""Shared request dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from app.context import AppContext, get_ctx
from app.http.errors import ApiError
from app.http.security import check_proxy_secret, session_id_from_cookie
from app.store import SessionRow

Ctx = Annotated[AppContext, Depends(get_ctx)]


def require_proxy(request: Request, ctx: Ctx) -> None:
    """Every /api route: only the Next.js proxy may call us (PRD 5.3)."""
    check_proxy_secret(request, ctx.settings.proxy_secret)


async def optional_session(request: Request, ctx: Ctx) -> SessionRow | None:
    session_id = session_id_from_cookie(request)
    if session_id is None:
        return None
    return await ctx.store.get_session(session_id)


async def current_session(
    session: Annotated[SessionRow | None, Depends(optional_session)],
) -> SessionRow:
    if session is None:
        raise ApiError(401, "no_session", "Start a session first.")
    return session


CurrentSession = Annotated[SessionRow, Depends(current_session)]
OptionalSession = Annotated[SessionRow | None, Depends(optional_session)]
