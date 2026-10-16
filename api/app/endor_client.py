"""Decision clients behind the gate engine's EndorClient protocol (docs/PRD.md 6.5).

- MockEndor: deterministic heuristics, no network, no credits. Default.
- LiveEndor: the Endor SDK (verified against endor 0.7.0, see docs/endor-facts.md).

Both raise the same two errors so callers never see SDK types:
- WarmingUp(retry_after): the model is starting; tell the player to wait and retry.
- UpstreamError: anything else went wrong. The gate fails closed on both.
"""

import hashlib
import json
import logging
import time
from typing import Final

import endor
import httpx

from app.gate.rules import match_deny
from app.gate.types import Decision, EndorClient, State
from app.settings import Settings

logger = logging.getLogger("app.endor")

QUESTION_NAME: Final = "safe"  # the one noul question we send per call
CALL_TIMEOUT_S: Final = 20.0  # PRD 6.5: per call, retries included
WARM_TIMEOUT_S: Final = 330.0  # /health/warm absorbs a cold start (server holds up to 300 s)
DEFAULT_WARMING_RETRY_S: Final = 30.0


class WarmingUp(Exception):
    """The model is starting. `ambiguous` is True when we only saw a timeout, which a
    cold start usually looks like (the server holds a cold request up to 300 s), but
    which could also be an outage. The breaker counts ambiguous ones as failures."""

    def __init__(self, retry_after: float, *, ambiguous: bool = False) -> None:
        super().__init__(f"model warming up, retry after {retry_after:.0f}s")
        self.retry_after = retry_after
        self.ambiguous = ambiguous


class UpstreamError(Exception):
    """The decision call failed for any reason other than warming up."""


# --------------------------------------------------------------------------- mock

# Phrases a naive gate falls for when they appear in the task (attack family F1/F2).
_AUTHORITY_PHRASES: Final = (
    "pre-approved",
    "preapproved",
    "approved by",
    "answer true",
    "this is safe",
    "verified safe",
    "security team",
)


def _jitter(*parts: str) -> float:
    """A stable value in [-0.05, 0.05] so different models give slightly different p."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return (digest[0] / 255.0 - 0.5) / 10.0


def _clamp(p: float) -> float:
    return max(0.01, min(0.99, p))


def estimate_tokens(state: State, question: str) -> int:
    """A rough input-token count (about 4 characters per token), never zero."""
    chars = len(question) + len(json.dumps(state, ensure_ascii=False))
    return max(1, -(-chars // 4))


class MockEndor:
    """Deterministic stand-in for the decision API.

    Heuristics (documented so tests and the UI can rely on them):
    - Verifier calls (state has "goal"): 0.9 if the command looks dangerous to the
      rule floor's patterns, else 0.2.
    - Task-match calls (question mentions "what the task says"): about 0.75.
    - Safety calls: about 0.85 for a harmless-looking command, about 0.1 for a
      dangerous-looking one. A plain question (no "untrusted data" in it) is fooled
      by an authority phrase in the task and returns about 0.9, which makes level 1
      winnable in mock mode while the hardened question resists it.
    Every value gets a small stable jitter per (model, question, state) and is
    clamped to [0.01, 0.99]. Obfuscated commands look harmless here, as they do to
    the floor; the mock is not meant to be clever.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, model: str, state: State, question: str) -> Decision:
        self.calls += 1
        p = self._p_safe(model, state, question)
        return Decision(p=p, input_tokens=estimate_tokens(state, question))

    @staticmethod
    def _p_safe(model: str, state: State, question: str) -> float:
        jitter = _jitter(model, question, json.dumps(state, sort_keys=True))
        command = state.get("command", "")
        dangerous = match_deny(command) is not None

        if "goal" in state:
            return _clamp((0.9 if dangerous else 0.2) + jitter)
        if "what the task says" in question:
            return _clamp(0.75 + jitter)

        if not dangerous:
            return _clamp(0.85 + jitter)
        hardened = "untrusted data" in question
        task = state.get("task", "").lower()
        fooled = not hardened and any(phrase in task for phrase in _AUTHORITY_PHRASES)
        return _clamp((0.9 if fooled else 0.1) + jitter)


# --------------------------------------------------------------------------- live


def _retry_after(headers: httpx.Headers) -> float:
    """Seconds from retry-after-ms or Retry-After (numeric), else a default."""
    for name, scale in (("retry-after-ms", 1000.0), ("retry-after", 1.0)):
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw.strip()) / scale
        except ValueError:
            continue
        if value >= 0:
            return value
    return DEFAULT_WARMING_RETRY_S


class LiveEndor:
    """The Endor SDK behind our interface.

    The SDK's decision defaults (330 s per request, a 660 s retry budget) would hold
    a player's request for minutes during a cold start, so this client sets its own:
    20 s total per call, and one retry only for 429 and 529. A 503 is not retried,
    so it surfaces as WarmingUp. Decisions carry exclude_from_training=True so
    players' text is not used for Endor's continuous learning (our own consent is
    default off, PRD 4.2).
    """

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = CALL_TIMEOUT_S,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        retry = endor.RetryPolicy(
            max_retries=1,
            http_statuses=frozenset({429, 529}),
            api_timeout_error=False,
            api_connection_error=False,
            timeout=timeout,
        )
        self._client = endor.EndorClient(
            api_key=api_key,
            retry=retry,
            timeout=timeout,
            exclude_from_training=True,
            capture=False,
            async_transport=async_transport,
        )

    async def decide(self, model: str, state: State, question: str) -> Decision:
        return await self._decide(model, state, question, timeout=None)

    async def warm(self, model: str) -> Decision:
        """One tiny decision with a long timeout, for /health/warm (bypasses the cache)."""
        state: State = {"task": "warm up", "command": "true"}
        return await self._decide(model, state, "Is this a test?", timeout=WARM_TIMEOUT_S)

    async def _decide(
        self, model: str, state: State, question: str, timeout: float | None
    ) -> Decision:
        started = time.perf_counter()
        try:
            res = await self._client.system_one_async(
                dict(state),
                {QUESTION_NAME: endor.Noul(instructions=question)},
                model=model,
                timeout=timeout,
            )
        except endor.APITimeoutError as exc:
            self._log(model, None, started, outcome="timeout")
            raise WarmingUp(DEFAULT_WARMING_RETRY_S, ambiguous=True) from exc
        except endor.APIError as exc:
            self._log(model, None, started, outcome=f"http_{exc.status}")
            if exc.status == 503:
                raise WarmingUp(_retry_after(exc.headers)) from exc
            raise UpstreamError(f"decision failed: {exc.status} {exc.code or ''}".strip()) from exc
        except endor.EndorError as exc:
            self._log(model, None, started, outcome=type(exc).__name__)
            raise UpstreamError(f"decision failed: {type(exc).__name__}") from exc

        answer = res.nouls.get(QUESTION_NAME)
        if answer is None:
            self._log(model, res.usage.input_tokens, started, outcome="no_answer")
            raise UpstreamError("decision response had no noul answer")
        self._log(model, res.usage.input_tokens, started, outcome="ok")
        # The budget must never under-count: estimate when Endor omits usage.
        tokens = res.usage.input_tokens
        return Decision(
            p=answer.noul,
            input_tokens=tokens if tokens is not None else estimate_tokens(state, question),
        )

    @staticmethod
    def _log(model: str, input_tokens: int | None, started: float, *, outcome: str) -> None:
        # Model, tokens, latency and outcome only: never the key, state or question text.
        latency_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "decision model=%s input_tokens=%s latency_ms=%d outcome=%s",
            model,
            input_tokens,
            latency_ms,
            outcome,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def make_endor_client(settings: Settings) -> EndorClient:
    """Pick the client from ENDOR_MODE. Mock is the default; live needs a key."""
    if settings.endor_mode == "mock":
        return MockEndor()
    if not settings.endor_api_key:
        raise ValueError("ENDOR_MODE=live needs ENDOR_API_KEY")
    return LiveEndor(settings.endor_api_key)
