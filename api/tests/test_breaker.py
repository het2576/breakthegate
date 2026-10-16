"""Circuit breaker tests: 5 failures in 60 s opens, half-open probe after 60 s."""

import asyncio

import pytest

from app.breaker import BreakerEndor, BreakerOpen, CircuitBreaker
from app.endor_client import UpstreamError, WarmingUp
from app.gate.types import Decision, State


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _breaker() -> tuple[CircuitBreaker, Clock]:
    clock = Clock()
    return CircuitBreaker(clock=clock), clock


def test_four_failures_stay_closed_fifth_opens() -> None:
    breaker, _ = _breaker()
    for _ in range(4):
        breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "open"
    with pytest.raises(BreakerOpen) as info:
        breaker.before_call()
    assert info.value.retry_after == pytest.approx(60.0)


def test_failures_outside_the_window_do_not_count() -> None:
    breaker, clock = _breaker()
    for _ in range(4):
        breaker.record_failure()
    clock.now += 61
    breaker.record_failure()
    assert breaker.state == "closed"


def test_success_while_closed_does_not_reset_the_window() -> None:
    breaker, _ = _breaker()
    for _ in range(4):
        breaker.record_failure()
        breaker.record_success()
    breaker.record_failure()
    assert breaker.state == "open"


def test_half_open_after_60s_allows_exactly_one_probe() -> None:
    breaker, clock = _breaker()
    for _ in range(5):
        breaker.record_failure()
    clock.now += 60
    assert breaker.state == "half_open"
    breaker.before_call()  # the probe
    with pytest.raises(BreakerOpen):
        breaker.before_call()  # everyone else still fails fast


def test_probe_success_closes() -> None:
    breaker, clock = _breaker()
    for _ in range(5):
        breaker.record_failure()
    clock.now += 60
    breaker.before_call()
    breaker.record_success()
    assert breaker.state == "closed"
    breaker.before_call()


def test_probe_failure_reopens_for_another_60s() -> None:
    breaker, clock = _breaker()
    for _ in range(5):
        breaker.record_failure()
    clock.now += 60
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == "open"
    clock.now += 59
    assert breaker.state == "open"
    clock.now += 1
    assert breaker.state == "half_open"


# --- BreakerEndor -----------------------------------------------------------


class Scripted:
    """Raises or returns the next scripted outcome on each call."""

    def __init__(self, outcomes: list[float | Exception]) -> None:
        self._outcomes = outcomes
        self.calls = 0

    async def decide(self, model: str, state: State, question: str) -> Decision:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return Decision(p=outcome)


def _run(client: BreakerEndor) -> float | Exception:
    try:
        return asyncio.run(client.decide("m", {"command": "ls"}, "q")).p
    except Exception as exc:  # noqa: BLE001 - tests inspect whatever came out
        return exc


def test_upstream_errors_open_and_then_skip_the_inner_client() -> None:
    inner = Scripted([UpstreamError("boom")] * 5)
    client = BreakerEndor(inner, CircuitBreaker(clock=Clock()))
    for _ in range(5):
        assert isinstance(_run(client), UpstreamError)
    assert isinstance(_run(client), BreakerOpen)
    assert inner.calls == 5  # the open breaker made no call


def test_plain_warming_is_not_a_failure() -> None:
    inner = Scripted([WarmingUp(30)] * 6)
    client = BreakerEndor(inner, CircuitBreaker(clock=Clock()))
    for _ in range(6):
        assert isinstance(_run(client), WarmingUp)
    assert client.breaker.state == "closed"


def test_ambiguous_warming_counts_as_failure() -> None:
    inner = Scripted([WarmingUp(30, ambiguous=True)] * 5)
    client = BreakerEndor(inner, CircuitBreaker(clock=Clock()))
    for _ in range(5):
        assert isinstance(_run(client), WarmingUp)
    assert client.breaker.state == "open"


def test_plain_warming_probe_lets_the_next_call_probe() -> None:
    clock = Clock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(5):
        breaker.record_failure()
    clock.now += 60
    inner = Scripted([WarmingUp(30), 0.8])
    client = BreakerEndor(inner, breaker)
    assert isinstance(_run(client), WarmingUp)  # probe ended without a verdict
    assert _run(client) == 0.8  # next call may probe, succeeds, closes
    assert breaker.state == "closed"
