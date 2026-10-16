"""Request trust: proxy secret, client IP, IP hashing, session cookie (PRD 5.3, 4.2).

The browser only reaches the API through the Next.js /api proxy, which sets
x-btg-proxy-secret and x-btg-client-ip. X-Forwarded-For is ignored entirely:
Render's load balancer appends to it and clients can forge its first entry.
"""

import hashlib
import hmac
import ipaddress
from datetime import date
from typing import Final
from uuid import UUID

from fastapi import Request, Response

from app.http.errors import ApiError

PROXY_SECRET_HEADER: Final = "x-btg-proxy-secret"  # noqa: S105 - a header name
CLIENT_IP_HEADER: Final = "x-btg-client-ip"
SESSION_COOKIE: Final = "btg_session"
SESSION_MAX_AGE_S: Final = 90 * 24 * 3600  # matches raw-attempt retention (PRD 4.2)


def check_proxy_secret(request: Request, expected: str) -> None:
    given = request.headers.get(PROXY_SECRET_HEADER, "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise ApiError(403, "forbidden", "Requests must come through the web app.")


def client_ip(request: Request) -> str | None:
    """The client IP as reported by our proxy, normalized, or None."""
    raw = request.headers.get(CLIENT_IP_HEADER, "").strip()
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def hash_ip(ip: str | None, seed: str, day: date) -> str | None:
    """A daily-rotating keyed hash: the same IP links within a day, not across days."""
    if ip is None:
        return None
    salt = hashlib.sha256(f"{seed}:{day.isoformat()}".encode()).digest()
    return hmac.new(salt, ip.encode(), hashlib.sha256).hexdigest()


def session_id_from_cookie(request: Request) -> UUID | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def set_session_cookie(response: Response, session_id: UUID, *, secure: bool) -> None:
    # No Domain attribute: host-only on the web origin, first party through the proxy.
    response.set_cookie(
        SESSION_COOKIE,
        str(session_id),
        max_age=SESSION_MAX_AGE_S,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=secure, samesite="lax")
