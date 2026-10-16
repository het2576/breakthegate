"""A fake decision client for gate-engine tests (no network, deterministic)."""

import asyncio
from collections.abc import Callable

from app.gate.types import Decision, State


def _always_safe(_model: str, _state: State, _question: str) -> float:
    return 1.0


class FakeClient:
    """Records calls and returns a p_safe chosen by a per-call function.

    decide_fn receives (model, state, question) and returns p_safe. Set `delay`
    to make calls overlap in time (for concurrency tests). Set `fail_models` to
    make decide raise for those model ids (for fail-closed and verifier tests).
    """

    def __init__(
        self,
        decide_fn: Callable[[str, State, str], float] | None = None,
        *,
        delay: float = 0.0,
        fail_models: set[str] | None = None,
    ) -> None:
        self._decide_fn = decide_fn or _always_safe
        self._delay = delay
        self._fail_models = fail_models or set()
        self.calls: list[tuple[str, State, str]] = []

    async def decide(self, model: str, state: State, question: str) -> Decision:
        self.calls.append((model, dict(state), question))
        if self._delay:
            await asyncio.sleep(self._delay)
        if model in self._fail_models:
            raise RuntimeError(f"model {model} unavailable")
        return Decision(p=self._decide_fn(model, state, question), input_tokens=10)
