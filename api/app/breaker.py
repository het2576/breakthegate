"""Circuit breaker for decision calls (docs/PRD.md 4.3, ARCHITECTURE 3.7).

Closed: calls go through. 5 failures within 60 s: open for 60 s, every call fails
fast with BreakerOpen ("The gate is resting") and costs nothing. After 60 s: half
open, exactly one probe call goes through. Probe succeeds: closed. Probe fails:
open again.

A plain WarmingUp (the server said 503 warming_up) is not a failure: the server
is starting, not broken. An ambiguous WarmingUp (only a timeout) is counted.
Single event loop, no awaits inside the state methods, so no locks are needed.
"""

import time
from collections import deque
from collections.abc import Callable
from typing import Final, Literal

from app.endor_client import WarmingUp
from app.gate.types import Decision, EndorClient, State

FAILURE_THRESHOLD: Final = 5
WINDOW_S: Final = 60.0
OPEN_S: Final = 60.0

BreakerState = Literal["closed", "open", "half_open"]


class BreakerOpen(Exception):
    """The breaker is open. Callers return 503 breaker_open with retry_after."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"breaker open, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class CircuitBreaker:
    def __init__(
        self,
        *,
        threshold: int = FAILURE_THRESHOLD,
        window_s: float = WINDOW_S,
        open_s: float = OPEN_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = threshold
        self._window_s = window_s
        self._open_s = open_s
        self._clock = clock
        self._failures: deque[float] = deque()
        self._opened_at: float | None = None
        self._probe_in_flight = False

    @property
    def state(self) -> BreakerState:
        if self._opened_at is None:
            return "closed"
        if self._clock() - self._opened_at >= self._open_s:
            return "half_open"
        return "open"

    def retry_after(self) -> float:
        """Seconds until the breaker half-opens (at least 1), for 503 breaker_open."""
        if self._opened_at is None:
            return 1.0
        return max(1.0, self._open_s - (self._clock() - self._opened_at))

    def before_call(self) -> None:
        """Raise BreakerOpen unless this call may proceed. Claims the probe when half open."""
        state = self.state
        if state == "closed":
            return
        if state == "half_open" and not self._probe_in_flight:
            self._probe_in_flight = True
            return
        opened_at = self._opened_at if self._opened_at is not None else self._clock()
        remaining = self._open_s - (self._clock() - opened_at)
        raise BreakerOpen(retry_after=max(1.0, remaining))

    def record_success(self) -> None:
        # While closed, a success does not wipe the window: the rule is "5 failures
        # in 60 s", not 5 in a row. A successful probe closes the breaker.
        if self._opened_at is not None or self._probe_in_flight:
            self._failures.clear()
            self._opened_at = None
            self._probe_in_flight = False

    def record_failure(self) -> None:
        now = self._clock()
        if self._probe_in_flight:  # the half-open probe failed: open again
            self._probe_in_flight = False
            self._opened_at = now
            return
        self._failures.append(now)
        while self._failures and now - self._failures[0] > self._window_s:
            self._failures.popleft()
        if len(self._failures) >= self._threshold:
            self._opened_at = now
            self._failures.clear()

    def release_probe(self) -> None:
        """A probe that ended without a verdict (plain warming): let the next call probe."""
        self._probe_in_flight = False


class BreakerEndor:
    """Wraps any EndorClient with a shared circuit breaker."""

    def __init__(self, inner: EndorClient, breaker: CircuitBreaker) -> None:
        self._inner = inner
        self.breaker = breaker

    async def decide(self, model: str, state: State, question: str) -> Decision:
        self.breaker.before_call()
        try:
            decision = await self._inner.decide(model, state, question)
        except WarmingUp as exc:
            if exc.ambiguous:
                self.breaker.record_failure()
            else:
                self.breaker.release_probe()
            raise
        except Exception:
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
        return decision
