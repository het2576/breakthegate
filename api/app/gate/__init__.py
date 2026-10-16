"""Gate engine: pure decision logic over an abstract decision client.

No network code lives here. Model layers depend only on the EndorClient
protocol (decide(model, state, question) -> Decision). See docs/PRD.md section 6.
"""

from app.gate.engine import evaluate_attempt, evaluate_gate, run_verifier
from app.gate.scoring import score_attempt
from app.gate.types import (
    Decision,
    EndorClient,
    GateDecision,
    GateState,
    LayerResult,
    State,
    VerifyResult,
)

__all__ = [
    "Decision",
    "EndorClient",
    "GateDecision",
    "GateState",
    "LayerResult",
    "State",
    "VerifyResult",
    "evaluate_attempt",
    "evaluate_gate",
    "run_verifier",
    "score_attempt",
]
