"""Sliding-window rate limits (docs/PRD.md 4.3): per session and per client IP.

In memory, per process: right for the single v1 API instance. If the API ever
scales out, move the counters to Postgres or Redis behind the same methods.
"""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self, limit: int, window_s: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._calls = 0

    def retry_after(self, key: str) -> float | None:
        """Seconds until `key` may act again, or None if it is under the limit now."""
        hits = self._prune(key, self._clock())
        if len(hits) < self._limit:
            return None
        return max(1.0, hits[0] + self._window_s - self._clock())

    def record(self, key: str) -> None:
        now = self._clock()
        self._prune(key, now).append(now)
        self._calls += 1
        if self._calls % 1000 == 0:
            self._sweep(now)

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window_s:
            hits.popleft()
        return hits

    def _sweep(self, now: float) -> None:
        for key in list(self._hits):
            if not self._prune(key, now):
                del self._hits[key]
