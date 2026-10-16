"""Gate composition and the goal verifier (docs/PRD.md sections 6.2, 6.3).

The rule floor runs first (pure, no network). Then the model layers and the
verifier start together. If the floor denies, the model layers are skipped but
the verifier still runs, so every attempt gets a goal label. Fail closed: if any
model layer errors or is warming, the exception propagates and the caller returns
503 with nothing stored. A win is approved AND verified.
"""

import asyncio

from app.gate.config import ConfigError, GateConfig, ResolvedLayer, ResolvedVerifier
from app.gate.rules import run_rule_floor
from app.gate.types import EndorClient, GateDecision, GateState, LayerResult, State, VerifyResult


async def _run_model_layer(layer: ResolvedLayer, state: State, client: EndorClient) -> LayerResult:
    # Config validation guarantees these for every served model layer; this guard
    # keeps the engine honest (and the types narrow) if that ever regresses.
    if layer.model_id is None or layer.question_text is None or layer.tau is None:
        raise ConfigError(f"model layer {layer.name!r} is not fully resolved")
    decision = await client.decide(layer.model_id, state, layer.question_text)
    p = decision.p
    passed = p >= layer.tau
    detail = (
        f"Probability safe {p:.2f}"
        if passed
        else f"Probability safe {p:.2f}, needs {layer.tau:.2f}"
    )
    return LayerResult(
        name=layer.name,
        passed=passed,
        p_safe=p,
        detail=detail,
        cache_hit=decision.cache_hit,
        input_tokens=decision.input_tokens,
    )


async def evaluate_gate(
    level: int, state: GateState, config: GateConfig, client: EndorClient
) -> GateDecision:
    """Run the layers for one level and compose the decision. Floor can only deny."""
    resolved = config.resolve_level(level)
    gate_input: State = {"task": state.task, "command": state.command}

    results: list[LayerResult] = []
    tau_by_name: dict[str, float] = {}
    floor_denied = False
    model_layers: list[ResolvedLayer] = []

    for layer in resolved.layers:
        if layer.type == "rule_floor":
            floor_result = run_rule_floor(state.command)
            results.append(floor_result)
            if not floor_result.passed:
                floor_denied = True
        else:
            if layer.tau is not None:  # always set for a served (unlocked) layer
                tau_by_name[layer.name] = layer.tau
            model_layers.append(layer)

    if not floor_denied and model_layers:
        gathered = await asyncio.gather(
            *(_run_model_layer(layer, gate_input, client) for layer in model_layers),
            return_exceptions=True,
        )
        for item in gathered:
            if isinstance(item, BaseException):
                raise item  # fail closed: a warming or failed model is never an approval
            results.append(item)

    return _compose(results, tau_by_name, config.version)


def _compose(
    results: list[LayerResult], tau_by_name: dict[str, float], version: str
) -> GateDecision:
    approved = all(r.passed for r in results)
    model_results = [r for r in results if r.p_safe is not None]
    p_values = [r.p_safe for r in results if r.p_safe is not None]
    # 0.0 when the floor denied before any model ran: the barrier stays closed.
    p_safe = min(p_values, default=0.0)

    if not approved:
        deciding = next(r for r in results if not r.passed)
    else:
        # The binding layer is the model closest to denying (lowest p_safe).
        deciding = min(model_results, key=lambda r: r.p_safe if r.p_safe is not None else 1.0)

    threshold = tau_by_name.get(deciding.name, 0.0)
    return GateDecision(
        approved=approved,
        p_safe=p_safe,
        threshold=threshold,
        deciding_layer=deciding.name,
        layers=results,
        gate_version=version,
    )


async def run_verifier(
    command: str, goal_text: str, config: GateConfig, client: EndorClient
) -> VerifyResult:
    """Check whether the command does the goal. Never sees the task. Fails closed."""
    verifier: ResolvedVerifier = config.resolve_verifier()
    verify_input: State = {"command": command, "goal": goal_text}
    try:
        decision = await client.decide(verifier.model_id, verify_input, verifier.question_text)
    except Exception as exc:  # noqa: BLE001 - any failure means unavailable; the caller fails closed
        # Duck-typed so the pure engine never imports client error types.
        retry_after = getattr(exc, "retry_after", None)
        return VerifyResult(
            verified=None,
            verify_p=None,
            retry_after=float(retry_after) if isinstance(retry_after, int | float) else None,
        )
    return VerifyResult(
        verified=decision.p >= verifier.tau_verify,
        verify_p=decision.p,
        cache_hit=decision.cache_hit,
        input_tokens=decision.input_tokens,
    )


async def evaluate_attempt(
    level: int, state: GateState, goal_text: str, config: GateConfig, client: EndorClient
) -> tuple[GateDecision, VerifyResult]:
    """Run the gate and the verifier concurrently on one attempt.

    The verifier runs even when the gate raises (so both calls settle with no
    orphan task), but a gate failure still propagates to the caller.
    """
    gate_task = evaluate_gate(level, state, config, client)
    verify_task = run_verifier(state.command, goal_text, config, client)
    gate_outcome, verify_outcome = await asyncio.gather(
        gate_task, verify_task, return_exceptions=True
    )
    if isinstance(gate_outcome, BaseException):
        raise gate_outcome
    if isinstance(verify_outcome, BaseException):
        raise verify_outcome  # unreachable: run_verifier catches its own failures
    return gate_outcome, verify_outcome
