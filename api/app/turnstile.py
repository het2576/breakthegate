"""Cloudflare Turnstile verification on session creation (PRD 2.? / P12).

No secret configured (dev, tests, before the founder sets one up in prod): every
session passes, so nothing here needs network access unless TURNSTILE_SECRET is set.
"""

from typing import Protocol

import httpx

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileVerifier(Protocol):
    async def verify(self, token: str | None, remote_ip: str | None) -> bool: ...


class NullVerifier:
    async def verify(self, token: str | None, remote_ip: str | None) -> bool:
        return True


class CloudflareVerifier:
    def __init__(self, secret: str, client: httpx.AsyncClient | None = None) -> None:
        self._secret = secret
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def verify(self, token: str | None, remote_ip: str | None) -> bool:
        if not token:
            return False
        data = {"secret": self._secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip
        try:
            resp = await self._client.post(VERIFY_URL, data=data)
            resp.raise_for_status()
        except httpx.HTTPError:
            return False
        body = resp.json()
        return bool(body.get("success"))

    async def aclose(self) -> None:
        await self._client.aclose()


def make_turnstile_verifier(secret: str | None) -> TurnstileVerifier:
    return CloudflareVerifier(secret) if secret else NullVerifier()
