"""Data types and the decision-client protocol for the gate engine.

docs/PRD.md section 6.1. The engine never imports the Endor SDK; it talks to
whatever satisfies EndorClient. The live and mock clients arrive in P2.
"""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

# The object a decision model sees. For gate layers it is {"task", "command"};
# for the verifier it is {"command", "goal"} (never the task). Values are strings.
State = dict[str, str]


class GateState(BaseModel):
    """The attacker-controlled text for one attempt."""

    task: str
    command: str


class LayerResult(BaseModel):
    """One layer's outcome, safe to show to the player."""

    name: str  # "rule_floor" | "model_a" | "model_b" | "task_match" | "tuned"
    passed: bool
    p_safe: float | None  # None for the rule floor
    detail: str  # short human text
    # Stored and logged, never returned to the browser:
    cache_hit: bool = False
    input_tokens: int = 0


class VerifyResult(BaseModel):
    """The goal verifier's outcome. verified is None only when it was unavailable."""

    verified: bool | None
    verify_p: float | None
    cache_hit: bool = False
    input_tokens: int = 0
    retry_after: float | None = None  # set when unavailable, if the client said how long


@dataclass(frozen=True)
class Decision:
    """One decision call's result. Cache hits cost nothing (input_tokens 0)."""

    p: float  # P(true) for the noul question, in [0, 1]
    input_tokens: int = 0
    cache_hit: bool = False


class GateDecision(BaseModel):
    """The composed gate decision for one attempt."""

    approved: bool
    p_safe: float  # the minimum p_safe across model layers (0.0 if the floor denied first)
    threshold: float
    deciding_layer: str
    layers: list[LayerResult]
    gate_version: str


class EndorClient(Protocol):
    """The only dependency the model layers have on the outside world."""

    async def decide(self, model: str, state: State, question: str) -> Decision:
        """Answer one noul question about one state: P(true) plus usage metadata.

        PRD 6.5 sketched this as returning a bare float; it returns a Decision so
        the cache can mark hits and the budget can count tokens (PRD 6.6, 4.3).
        """
        ...
