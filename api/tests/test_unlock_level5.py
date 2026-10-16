"""The Level 5 release guard only accepts saved, predeclared evidence."""

import importlib.util
from typing import Any

import pytest


def _module() -> Any:
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "ml" / "scripts" / "unlock_level5.py"
    spec = importlib.util.spec_from_file_location("unlock_level5", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gates() -> dict[str, Any]:
    return {
        "version": "gate-v2",
        "models": {"T": {"id": "gate/hardened", "trained_question_sha256": "a" * 64}},
        "levels": {5: {"locked": True, "layers": [{"name": "tuned", "model": "T", "tau": 0.7}]}},
    }


def _passed_eval() -> dict[str, Any]:
    return {
        "level5": {
            "status": "pass",
            "model": "gate/hardened",
            "tau": 0.7,
            "trained_question_sha256": "a" * 64,
            "gate_version": "gate-v2",
            "success": {
                "held_out_asr_drop": 0.10,
                "intervals_do_not_overlap": True,
                "clean_safe_fbr_increase": 0.02,
                "benign_scary_fbr_increase": 0.02,
                "beats_control_t1": True,
                "calibration_note": "ECE was unchanged.",
            },
        }
    }


def test_level_five_requires_all_success_criteria() -> None:
    module = _module()
    assert module.decide(_passed_eval(), _gates()).action == "unlock"
    failed = _passed_eval()
    failed["level5"]["success"]["beats_control_t1"] = False
    with pytest.raises(ValueError, match="beats_control_t1"):
        module.decide(failed, _gates())


def test_negative_result_is_explicitly_kept_locked() -> None:
    module = _module()
    assert (
        module.decide({"level5": {"status": "negative_result"}}, _gates()).action == "stay_locked"
    )
