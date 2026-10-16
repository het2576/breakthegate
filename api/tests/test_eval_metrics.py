"""Deterministic checks for the offline gate-evaluation core."""

import importlib.util
from pathlib import Path
from typing import Any


def _module() -> Any:
    path = Path(__file__).resolve().parents[2] / "ml" / "scripts" / "eval.py"
    spec = importlib.util.spec_from_file_location("gate_eval", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tau_obeys_validation_false_block_cap() -> None:
    module = _module()
    assert module.pick_tau([0.99, 0.98, 0.97, 0.01]) == 0.01
    assert module.pick_tau([0.99] * 50) == 0.99


def test_bootstrap_is_seeded_and_auc_handles_ties() -> None:
    module = _module()

    def metric(values: list[float]) -> float:
        return sum(values) / len(values)

    first = module.bootstrap([0.1, 0.9], metric, seed=4, n=100)
    second = module.bootstrap([0.1, 0.9], metric, seed=4, n=100)
    assert first == second
    P = module.Prediction
    rows = [P("a", "test", "clean", True, 0.5), P("b", "test", "clean", False, 0.5)]
    assert module.auroc(rows) == 0.5
