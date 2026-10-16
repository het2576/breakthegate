"""Config loader tests (docs/PRD.md section 6.4). The loader must refuse to start
on any violation rather than risk a silent approval."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from app.gate.config import ConfigError, GateConfig, GatesConfig, load_config

# Placeholder question texts: these tests exercise the loader's rules, not the
# wording. The real q0/q1 content is checked separately via load_config().
Q0 = "plain safe question"
Q1 = "hardened question text"
MATCH = "match question text"
VERIFY = "verify question text"


def _base(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "version": "test.1",
        "questions": {"safe_q0": Q0, "safe_q1": Q1, "match": MATCH, "verify": VERIFY},
        "models": {
            "A": {"id": "gate/a"},
            "V": {"id": "gate/v", "question": "verify", "tau_verify": 0.8},
            "T": {"id": None, "trained_question_sha256": None},
        },
        "levels": {
            1: {
                "layers": [
                    {
                        "name": "model_a",
                        "type": "model",
                        "model": "A",
                        "question": "safe_q0",
                        "tau": 0.5,
                    }
                ]
            },
        },
    }
    cfg.update(overrides)
    return cfg


def _build(cfg: dict[str, Any]) -> GateConfig:
    return GateConfig(GatesConfig.model_validate(cfg))


def test_real_config_loads() -> None:
    config = load_config()
    assert config.version
    for level in (1, 2, 3, 4, 5):
        config.resolve_level(level)
    config.resolve_verifier()


def test_levels_1_and_2_resolve_safe_q0() -> None:
    config = load_config()
    for level in (1, 2):
        safe_layers = [
            layer for layer in config.resolve_level(level).layers if layer.name == "model_a"
        ]
        assert safe_layers[0].question_text.startswith("Is it safe")  # type: ignore[union-attr]
        assert "untrusted data" not in (safe_layers[0].question_text or "")


def test_levels_3_to_5_resolve_safe_q1() -> None:
    config = load_config()
    for level in (3, 4, 5):
        safe_layers = [
            layer
            for layer in config.resolve_level(level).layers
            if layer.name in {"model_a", "model_b", "tuned"}
        ]
        for layer in safe_layers:
            assert "untrusted data" in (layer.question_text or "")


def test_wrong_question_for_level_is_rejected() -> None:
    cfg = _base()
    cfg["levels"][1]["layers"][0]["question"] = "safe_q1"
    with pytest.raises(ConfigError, match="must use 'safe_q0'"):
        _build(cfg)


def test_task_match_must_use_match_question() -> None:
    cfg = _base()
    cfg["levels"][3] = {
        "layers": [
            {"name": "model_a", "type": "model", "model": "A", "question": "safe_q1", "tau": 0.5},
            {
                "name": "task_match",
                "type": "task_match",
                "model": "A",
                "question": "safe_q1",
                "tau": 0.5,
            },
        ]
    }
    with pytest.raises(ConfigError, match="task_match must use"):
        _build(cfg)


def test_unlocked_level_missing_tau_is_rejected() -> None:
    cfg = _base()
    del cfg["levels"][1]["layers"][0]["tau"]
    with pytest.raises(ConfigError, match="needs a tau"):
        _build(cfg)


def test_unlocked_level_missing_model_id_is_rejected() -> None:
    cfg = _base()
    cfg["models"]["A"]["id"] = None
    with pytest.raises(ConfigError, match="needs a model id"):
        _build(cfg)


def test_tuned_question_hash_mismatch_is_rejected() -> None:
    cfg = _base()
    cfg["models"]["T"] = {"id": "gate/tuned", "trained_question_sha256": "0" * 64}
    cfg["levels"][5] = {
        "layers": [
            {"name": "tuned", "type": "model", "model": "T", "question": "safe_q1", "tau": 0.5}
        ]
    }  # unlocked, so it must be served and the hash must match
    with pytest.raises(ConfigError, match="trained question hash"):
        _build(cfg)


def test_tuned_question_hash_match_is_accepted() -> None:
    cfg = _base()
    good = hashlib.sha256(Q1.encode("utf-8")).hexdigest()
    cfg["models"]["T"] = {"id": "gate/tuned", "trained_question_sha256": good}
    cfg["levels"][5] = {
        "layers": [
            {"name": "tuned", "type": "model", "model": "T", "question": "safe_q1", "tau": 0.5}
        ]
    }
    config = _build(cfg)
    assert config.resolve_level(5).layers[0].model_id == "gate/tuned"


def test_locked_level_with_untrained_tuned_model_is_allowed() -> None:
    # The real config: level 5 locked, T.id null. Must load without error.
    config = load_config()
    assert config.resolve_level(5).locked is True


def test_verifier_without_id_is_rejected() -> None:
    cfg = _base()
    cfg["models"]["V"]["id"] = None
    with pytest.raises(ConfigError, match="model V has no id"):
        _build(cfg)


def test_unknown_question_key_is_rejected() -> None:
    cfg = _base()
    cfg["levels"][1]["layers"][0]["question"] = "nope"
    with pytest.raises(ConfigError, match="unknown question"):
        _build(cfg)


def test_unknown_model_key_is_rejected() -> None:
    cfg = _base()
    cfg["levels"][1]["layers"][0]["model"] = "Z"
    with pytest.raises(ConfigError, match="unknown model"):
        _build(cfg)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.yaml")


def test_invalid_schema_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "gates.yaml"
    bad.write_text("version: x\nquestions: {}\nmodels: {}\nlevels: {}\nsurprise: 1\n")
    with pytest.raises(ConfigError, match="invalid"):
        load_config(bad)


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown level"):
        load_config().resolve_level(99)


def test_price_lookup_and_conservative_fallback() -> None:
    config = load_config()
    assert config.usd_per_mtok("gate/decider-2b") == 0.007
    assert config.usd_per_mtok("unknown/model") == 0.042  # unknown: highest published rate
