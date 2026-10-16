"""Gate engine tests: composition per level, verifier behavior, fail-closed."""

import asyncio
import time

import pytest

from app.gate.config import load_config
from app.gate.engine import evaluate_attempt, evaluate_gate, run_verifier
from app.gate.types import GateState, State
from tests.fakes import FakeClient

CONFIG = load_config()
SAFE = GateState(task="clean the build cache", command="rm -rf ./dist")
DANGEROUS = GateState(task="tidy up", command="rm -rf /etc")


def _const(p: float) -> FakeClient:
    return FakeClient(lambda _m, _s, _q: p)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_all_layers_pass_approves(level: int) -> None:
    decision = asyncio.run(evaluate_gate(level, SAFE, CONFIG, _const(0.99)))
    assert decision.approved is True
    assert all(layer.passed for layer in decision.layers)
    assert decision.gate_version == CONFIG.version


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_any_model_below_tau_denies(level: int) -> None:
    decision = asyncio.run(evaluate_gate(level, SAFE, CONFIG, _const(0.10)))
    assert decision.approved is False
    assert decision.p_safe == pytest.approx(0.10)


def test_floor_denies_and_skips_models_at_level_2() -> None:
    # Model would approve, but the floor hits on a dangerous command.
    client = _const(0.99)
    decision = asyncio.run(evaluate_gate(2, DANGEROUS, CONFIG, client))
    assert decision.approved is False
    assert decision.deciding_layer == "rule_floor"
    assert decision.p_safe == 0.0  # no model ran, barrier stays closed
    # The model layer was skipped, so the client saw no gate call.
    assert client.calls == []


def test_floor_can_never_approve_on_its_own() -> None:
    # Level 1 has no floor; level 2 adds it. The floor only ever subtracts.
    client = _const(0.99)
    lvl1 = asyncio.run(evaluate_gate(1, SAFE, CONFIG, client))
    lvl2 = asyncio.run(evaluate_gate(2, SAFE, CONFIG, _const(0.99)))
    assert lvl1.approved and lvl2.approved  # floor passes a safe command
    # On a dangerous command the floor forces denial regardless of the model.
    forced = asyncio.run(evaluate_gate(2, DANGEROUS, CONFIG, _const(0.99)))
    assert forced.approved is False


def test_deciding_layer_is_first_failing_layer() -> None:
    # Level 4: model_a passes, model_b fails -> model_b decides.
    def decide(model: str, _s: State, _q: str) -> float:
        return 0.9 if model == "gate/decider-2b" else 0.2

    decision = asyncio.run(evaluate_gate(4, SAFE, CONFIG, FakeClient(decide)))
    assert decision.approved is False
    assert decision.deciding_layer == "model_b"
    assert decision.threshold == pytest.approx(0.5)


def test_deciding_layer_on_approval_is_lowest_p() -> None:
    def decide(model: str, _s: State, _q: str) -> float:
        return 0.95 if model == "gate/decider-2b" else 0.70

    decision = asyncio.run(evaluate_gate(4, SAFE, CONFIG, FakeClient(decide)))
    assert decision.approved is True
    assert decision.deciding_layer == "model_b"  # 0.70 is the binding constraint
    assert decision.p_safe == pytest.approx(0.70)


def test_level_3_uses_task_match_question() -> None:
    client = _const(0.99)
    asyncio.run(evaluate_gate(3, SAFE, CONFIG, client))
    questions = {call[2] for call in client.calls}
    assert CONFIG._question_text("match", "test") in questions  # pyright: ignore[reportPrivateUsage]
    assert CONFIG._question_text("safe_q1", "test") in questions  # pyright: ignore[reportPrivateUsage]


def test_fail_closed_when_a_model_errors() -> None:
    client = FakeClient(lambda _m, _s, _q: 0.99, fail_models={"gate/decider-2b"})
    with pytest.raises(RuntimeError):
        asyncio.run(evaluate_gate(1, SAFE, CONFIG, client))


# --- Verifier ---------------------------------------------------------------


def test_verifier_runs_and_passes_above_tau() -> None:
    result = asyncio.run(run_verifier("rm -rf /etc", "delete a directory", CONFIG, _const(0.9)))
    assert result.verified is True
    assert result.verify_p == pytest.approx(0.9)


def test_verifier_fails_closed_to_none_on_error() -> None:
    client = FakeClient(fail_models={"gate/pplx-decider-v1.1-27b"})
    result = asyncio.run(run_verifier("rm -rf /etc", "delete a directory", CONFIG, client))
    assert result.verified is None
    assert result.verify_p is None


def test_verifier_never_receives_the_task() -> None:
    client = _const(0.9)
    asyncio.run(
        evaluate_attempt(
            1, GateState(task="SECRET-TASK-TOKEN", command="rm -rf /etc"), "goal", CONFIG, client
        )
    )
    verifier_calls = [c for c in client.calls if c[0] == "gate/pplx-decider-v1.1-27b"]
    assert len(verifier_calls) == 1
    _model, state, _q = verifier_calls[0]
    assert "task" not in state
    assert set(state) == {"command", "goal"}


def test_verifier_runs_even_when_floor_denies() -> None:
    client = _const(0.9)
    _decision, verify = asyncio.run(
        evaluate_attempt(2, DANGEROUS, "delete a directory", CONFIG, client)
    )
    assert verify.verified is True  # the verifier ran despite the floor deny
    verifier_calls = [c for c in client.calls if c[0] == "gate/pplx-decider-v1.1-27b"]
    assert len(verifier_calls) == 1


def test_verifier_runs_concurrently_with_model_layers() -> None:
    # Four calls at level 4 (floor + 2 models + verifier). With a 50 ms delay each,
    # sequential would be >= 150 ms; concurrent is close to one delay.
    client = FakeClient(lambda _m, _s, _q: 0.9, delay=0.05)
    start = time.perf_counter()
    asyncio.run(evaluate_attempt(4, SAFE, "goal", CONFIG, client))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.12, f"calls did not overlap: {elapsed:.3f}s"


def test_attempt_gate_failure_propagates_but_verifier_still_settles() -> None:
    client = FakeClient(lambda _m, _s, _q: 0.9, fail_models={"gate/decider-2b"})
    with pytest.raises(RuntimeError):
        asyncio.run(evaluate_attempt(1, SAFE, "goal", CONFIG, client))
    # The verifier call was still issued (no orphaned/un-awaited task).
    assert any(c[0] == "gate/pplx-decider-v1.1-27b" for c in client.calls)


def test_layers_record_cache_hit_and_tokens() -> None:
    from app.cache import CachedEndor

    client = CachedEndor(_const(0.9), CONFIG.version)
    first, _ = asyncio.run(evaluate_attempt(1, SAFE, "goal", CONFIG, client))
    second, verify = asyncio.run(evaluate_attempt(1, SAFE, "goal", CONFIG, client))
    assert first.layers[0].cache_hit is False and first.layers[0].input_tokens == 10
    assert second.layers[0].cache_hit is True and second.layers[0].input_tokens == 0
    assert verify.cache_hit is True


def test_verifier_passes_through_retry_after_when_unavailable() -> None:
    from app.endor_client import WarmingUp

    class Warming:
        async def decide(self, model: str, state: State, question: str):  # noqa: ANN201
            raise WarmingUp(42)

    result = asyncio.run(run_verifier("ls", "goal", CONFIG, Warming()))
    assert result.verified is None and result.retry_after == 42
