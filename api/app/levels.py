"""The public description of the levels (docs/PRD.md 3.3, 3.5).

Transparency is the point: players see every check, the exact question each
model is asked, and the threshold it needs. Model ids never appear here
(confidential, PRD 4.5).
"""

from typing import Any, Final

from app.gate.config import GateConfig
from app.goals import GOALS
from app.store import LevelProgress

_LABELS: Final = {
    "rule_floor": "Pattern filter",
    "model_a": "Model A",
    "model_b": "Model B",
    "task_match": "Task match",
    "tuned": "Hardened model",
}
LOCKED_TEXT: Final = "Unlocks when the hardened gate is ready"


def public_levels(
    config: GateConfig, progress: dict[int, LevelProgress] | None = None
) -> dict[str, Any]:
    levels: list[dict[str, Any]] = []
    for number in sorted(config.levels):
        resolved = config.resolve_level(number)
        vault = (progress or {}).get(number, LevelProgress(0, 0))
        layers: list[dict[str, Any]] = []
        for layer in resolved.layers:
            if layer.type == "rule_floor":
                layers.append(
                    {
                        "name": layer.name,
                        "label": _LABELS["rule_floor"],
                        "kind": "rule_floor",
                        "question": None,
                        "threshold": None,
                        "description": "Checks your command for known dangerous patterns. "
                        "It can only say no.",
                    }
                )
                continue
            label = _LABELS.get(layer.name, layer.name)
            layers.append(
                {
                    "name": layer.name,
                    "label": label,
                    "kind": layer.type,
                    "question": layer.question_text,
                    "threshold": layer.tau,
                    "description": f"{label} must answer yes with probability "
                    f"{layer.tau:.2f} or more."
                    if layer.tau is not None
                    else None,
                }
            )
        levels.append(
            {
                "level": number,
                "name": config.levels[number].name,
                "locked": resolved.locked,
                "locked_text": LOCKED_TEXT if resolved.locked else None,
                "rule": "Every check must say yes.",
                "layers": layers,
                "players_tried": vault.players_tried,
                "winners": vault.winners,
            }
        )

    verifier = config.resolve_verifier()
    return {
        "gate_version": config.version,
        "levels": levels,
        "goals": [{"id": goal_id, "text": text} for goal_id, text in GOALS.items()],
        "goal_check": {
            "question": verifier.question_text,
            "threshold": verifier.tau_verify,
            "description": "A separate check reads only your command and the goal. "
            "Only approved commands that really do the goal score.",
        },
    }
