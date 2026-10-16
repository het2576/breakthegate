"""Anonymous sessions: create, read, update consent or handle, delete (PRD 4.2, 7).

The session id lives only in an httpOnly cookie; it is never in a response body.
Consent defaults to off.
"""

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator

from app.budget import utc_today
from app.http.errors import ApiError
from app.http.security import clear_session_cookie, client_ip, hash_ip, set_session_cookie
from app.moderation import handle_problem
from app.routes.deps import Ctx, CurrentSession, OptionalSession
from app.store import UNSET, SessionRow, Unset

router = APIRouter()


def _clean_handle(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    problem = handle_problem(value)
    if problem:
        raise ValueError(problem)
    return value


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str | None = None
    consent_training: bool = False
    turnstile_token: str | None = None

    _handle = field_validator("handle")(_clean_handle)


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str | None = None
    consent_training: bool | None = None

    _handle = field_validator("handle")(_clean_handle)


def _out(session: SessionRow) -> dict[str, Any]:
    return {
        "session": {
            "handle": session.handle,
            "consent_training": session.consent_training,
            "created_at": session.created_at.isoformat(),
        }
    }


@router.post("/sessions", status_code=201)
async def create_session(
    body: SessionIn, request: Request, response: Response, ctx: Ctx, existing: OptionalSession
) -> dict[str, Any]:
    if existing is not None:
        response.status_code = 200
        return _out(existing)
    ip = client_ip(request)
    if not await ctx.turnstile.verify(body.turnstile_token, ip):
        raise ApiError(403, "turnstile_failed", "That check did not pass. Reload and try again.")
    ip_hash = hash_ip(ip, ctx.settings.ip_hash_salt_seed, utc_today())
    session = await ctx.store.create_session(
        handle=body.handle, consent_training=body.consent_training, ip_hash=ip_hash
    )
    set_session_cookie(response, session.id, secure=ctx.settings.cookie_secure)
    return _out(session)


@router.get("/sessions/me")
async def get_session(session: CurrentSession) -> dict[str, Any]:
    return _out(session)


@router.patch("/sessions/me")
async def update_session(body: SessionPatch, session: CurrentSession, ctx: Ctx) -> dict[str, Any]:
    handle: str | None | Unset = body.handle if "handle" in body.model_fields_set else UNSET
    consent: bool | Unset = body.consent_training if body.consent_training is not None else UNSET
    updated = await ctx.store.update_session(session.id, handle=handle, consent_training=consent)
    return _out(updated or session)


@router.post("/sessions/me/delete")
async def delete_session(session: CurrentSession, response: Response, ctx: Ctx) -> dict[str, Any]:
    await ctx.store.delete_session(session.id)
    clear_session_cookie(response, secure=ctx.settings.cookie_secure)
    return {"deleted": True}
