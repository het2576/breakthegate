"""Probability cache for decision calls (docs/PRD.md 6.6). API only: ml/ never uses it.

Key: SHA-256 of model id, question text, canonical state JSON and gate version.
Canonical means sorted keys and compact separators; string values are NOT
changed (no case folding, whitespace collapse or Unicode normalization), because
those would change what the model sees. TTL 24 h, in-memory LRU per process,
bounded. Only successful probabilities are cached; errors propagate uncached.
"""

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Final

from app.gate.types import Decision, EndorClient, State

TTL_S: Final = 24 * 3600.0
MAX_ENTRIES: Final = 50_000


def cache_key(model: str, question: str, state: State, gate_version: str) -> str:
    canonical = json.dumps(
        [model, question, state, gate_version],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CachedEndor:
    """Serves repeat decisions from memory. A hit is marked and costs nothing."""

    def __init__(
        self,
        inner: EndorClient,
        gate_version: str,
        *,
        ttl_s: float = TTL_S,
        max_entries: int = MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._gate_version = gate_version
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, float]] = OrderedDict()  # key -> (expires, p)

    def __len__(self) -> int:
        return len(self._entries)

    async def decide(self, model: str, state: State, question: str) -> Decision:
        key = cache_key(model, question, state, self._gate_version)
        cached = self._get(key)
        if cached is not None:
            return Decision(p=cached, input_tokens=0, cache_hit=True)
        decision = await self._inner.decide(model, state, question)
        self._put(key, decision.p)
        return decision

    def _get(self, key: str) -> float | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires, p = entry
        if self._clock() >= expires:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return p

    def _put(self, key: str, p: float) -> None:
        self._entries[key] = (self._clock() + self._ttl_s, p)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
