"""Cloudflare Turnstile verification (P12)."""

import httpx
import pytest

from app.turnstile import CloudflareVerifier, NullVerifier, make_turnstile_verifier

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_null_verifier_always_passes() -> None:
    assert make_turnstile_verifier(None) is not None
    assert isinstance(make_turnstile_verifier(None), NullVerifier)
    assert await NullVerifier().verify(None, None) is True


async def test_cloudflare_verifier_needs_a_token() -> None:
    verifier = CloudflareVerifier("secret")
    assert await verifier.verify(None, "1.2.3.4") is False
    await verifier.aclose()


async def test_cloudflare_verifier_reports_success_and_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        ok = "response=good" in body
        return httpx.Response(200, json={"success": ok})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    verifier = CloudflareVerifier("secret", client=client)
    assert await verifier.verify("good", "1.2.3.4") is True
    assert await verifier.verify("bad", "1.2.3.4") is False
    await verifier.aclose()


async def test_cloudflare_verifier_fails_closed_on_network_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = CloudflareVerifier("secret", client=client)
    assert await verifier.verify("good", "1.2.3.4") is False
    await verifier.aclose()
