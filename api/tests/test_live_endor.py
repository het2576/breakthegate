"""LiveEndor tests against a fake HTTP transport (no network, no credits).

They pin our wrapper to the real SDK's behavior: request shape, the 503 and
timeout mapping, our retry policy, and log hygiene.
"""

import asyncio
import json
import logging
from collections.abc import Callable

import httpx
import pytest

from app.endor_client import LiveEndor, UpstreamError, WarmingUp

KEY = "edk_test_never_logged_123"
STATE = {"task": "clean the build cache", "command": "rm -rf ./dist"}
Handler = Callable[[httpx.Request], httpx.Response]


def _ok(p: float = 0.73, tokens: int = 120) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "gate/decider-2b",
            "answers": {"safe": {"type": "noul", "noul": p}},
            "usage": {"input_tokens": tokens},
        },
    )


class Recorder:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.url.path == "/v1/systemone"
        outcome = self._responses[len(self.requests) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _decide(handler: Handler) -> float:
    async def go() -> float:
        client = LiveEndor(KEY, async_transport=httpx.MockTransport(handler))
        try:
            return (await client.decide("gate/decider-2b", STATE, "Is it safe?")).p
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_success_returns_the_noul_probability() -> None:
    assert _decide(Recorder([_ok(0.73)])) == pytest.approx(0.73)


def test_request_shape_and_training_opt_out() -> None:
    rec = Recorder([_ok()])
    _decide(rec)
    body = json.loads(rec.requests[0].content)
    assert body["model"] == "gate/decider-2b"
    assert body["state"] == STATE
    assert body["questions"] == {"safe": {"type": "noul", "instructions": "Is it safe?"}}
    assert body["exclude_from_training"] is True


def test_503_warming_up_maps_to_warming_with_retry_after() -> None:
    warming = httpx.Response(
        503,
        json={"error": {"code": "warming_up", "message": "starting"}},
        headers={"retry-after": "45"},
    )
    rec = Recorder([warming])
    with pytest.raises(WarmingUp) as info:
        _decide(rec)
    assert info.value.retry_after == pytest.approx(45)
    assert info.value.ambiguous is False
    assert len(rec.requests) == 1  # 503 is not retried by the SDK under our policy


def test_timeout_maps_to_ambiguous_warming() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(WarmingUp) as info:
        _decide(timeout)
    assert info.value.ambiguous is True


def test_429_is_retried_once() -> None:
    limited = httpx.Response(
        429,
        json={"error": {"code": "rate_limited", "message": "slow down"}},
        headers={"retry-after-ms": "1"},
    )
    rec = Recorder([limited, _ok(0.6)])
    assert _decide(rec) == pytest.approx(0.6)
    assert len(rec.requests) == 2


def test_500_is_an_upstream_error_without_retry() -> None:
    rec = Recorder([httpx.Response(500, json={"error": {"code": "internal", "message": "x"}})])
    with pytest.raises(UpstreamError):
        _decide(rec)
    assert len(rec.requests) == 1


def test_auth_error_is_an_upstream_error() -> None:
    rec = Recorder([httpx.Response(401, json={"error": {"code": "unauthorized", "message": "x"}})])
    with pytest.raises(UpstreamError):
        _decide(rec)


def test_missing_answer_is_an_upstream_error() -> None:
    empty = httpx.Response(200, json={"model": "gate/decider-2b", "answers": {}})
    with pytest.raises(UpstreamError):
        _decide(Recorder([empty]))


def test_logs_never_contain_the_key_state_or_question(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    _decide(Recorder([_ok(0.73, tokens=120)]))
    assert KEY not in caplog.text
    assert "rm -rf ./dist" not in caplog.text
    assert "Is it safe?" not in caplog.text
    ours = [r.getMessage() for r in caplog.records if r.name == "app.endor"]
    assert ours and "input_tokens=120" in ours[0] and "latency_ms=" in ours[0]


def test_connection_error_is_an_upstream_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(UpstreamError):
        _decide(refuse)


def test_unparseable_retry_after_falls_back_to_default() -> None:
    warming = httpx.Response(
        503,
        json={"error": {"code": "warming_up", "message": "starting"}},
        headers={"retry-after": "soon"},
    )
    with pytest.raises(WarmingUp) as info:
        _decide(Recorder([warming]))
    assert info.value.retry_after == pytest.approx(30)


def test_warm_sends_one_tiny_decision() -> None:
    rec = Recorder([_ok(0.5)])

    async def go() -> float:
        client = LiveEndor(KEY, async_transport=httpx.MockTransport(rec))
        try:
            return (await client.warm("gate/decider-2b")).p
        finally:
            await client.aclose()

    assert asyncio.run(go()) == pytest.approx(0.5)
    body = json.loads(rec.requests[0].content)
    assert body["model"] == "gate/decider-2b"
    assert "task" in body["state"]  # a fixed, harmless warm-up state
