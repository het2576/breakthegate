"""Typed loader for api/config/gates.yaml (docs/PRD.md section 6.4).

The loader refuses to start on any config violation, so a misconfigured gate can
never silently approve. All thresholds, question texts and model ids come from
here, never hardcoded.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

LayerType = Literal["rule_floor", "model", "task_match"]

# Which safe-judgment question each level must use (PRD 6.4). task_match is exempt.
_SAFE_QUESTION_BY_LEVEL: dict[int, str] = {
    1: "safe_q0",
    2: "safe_q0",
    3: "safe_q1",
    4: "safe_q1",
    5: "safe_q1",
}
_SAFE_LAYER_NAMES = {"model_a", "model_b", "tuned"}

# Highest decision price in the public docs (PRD 9): the budget fallback.
MAX_PUBLISHED_USD_PER_MTOK = 0.042

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "gates.yaml"


class ConfigError(ValueError):
    """Raised when gates.yaml is invalid. The API must not start."""


class ModelCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    question: str | None = None  # only the verifier pins its question here
    tau_verify: float | None = None
    trained_question_sha256: str | None = None
    usd_per_mtok: float | None = None  # decision price per 1M input tokens


class LayerCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: LayerType
    model: str | None = None
    question: str | None = None
    tau: float | None = None


class LevelCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    locked: bool = False
    layers: list[LayerCfg]


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    questions: dict[str, str]
    models: dict[str, ModelCfg]
    levels: dict[int, LevelCfg]


@dataclass(frozen=True)
class ResolvedLayer:
    name: str
    type: LayerType
    model_id: str | None  # None only for rule_floor
    question_text: str | None  # None only for rule_floor
    tau: float | None  # None only for rule_floor, or a locked tuned layer


@dataclass(frozen=True)
class ResolvedLevel:
    level: int
    locked: bool
    layers: tuple[ResolvedLayer, ...]


@dataclass(frozen=True)
class ResolvedVerifier:
    model_id: str
    question_text: str
    tau_verify: float


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GateConfig:
    """Validated gate configuration, ready for the engine."""

    def __init__(self, raw: GatesConfig) -> None:
        self._raw = raw
        self.version = raw.version
        self._validate()

    @property
    def levels(self) -> dict[int, LevelCfg]:
        return self._raw.levels

    def _question_text(self, key: str | None, where: str) -> str:
        if key is None:
            raise ConfigError(f"{where}: missing question key")
        if key not in self._raw.questions:
            raise ConfigError(f"{where}: unknown question {key!r}")
        return self._raw.questions[key]

    def _model(self, key: str | None, where: str) -> ModelCfg:
        if key is None:
            raise ConfigError(f"{where}: missing model key")
        if key not in self._raw.models:
            raise ConfigError(f"{where}: unknown model {key!r}")
        return self._raw.models[key]

    def _validate(self) -> None:
        for level, cfg in self._raw.levels.items():
            for layer in cfg.layers:
                self._validate_layer(level, cfg.locked, layer)
        # The verifier must always be resolvable: the gate runs it on every attempt.
        self.resolve_verifier()

    def _validate_layer(self, level: int, locked: bool, layer: LayerCfg) -> None:
        where = f"level {level} layer {layer.name!r}"
        if layer.type == "rule_floor":
            return

        model = self._model(layer.model, where)
        question_text = self._question_text(layer.question, where)

        if layer.type == "task_match":
            if layer.question != "match":
                raise ConfigError(f"{where}: task_match must use the 'match' question")
        elif layer.name in _SAFE_LAYER_NAMES:
            expected = _SAFE_QUESTION_BY_LEVEL.get(level)
            if expected is not None and layer.question != expected:
                raise ConfigError(
                    f"{where}: level {level} must use {expected!r}, got {layer.question!r}"
                )

        # A tuned model must be served with the exact question it was trained with.
        if layer.model == "T":
            self._validate_tuned(where, locked, model, question_text)

        if not locked:
            if model.id is None:
                raise ConfigError(f"{where}: unlocked level needs a model id")
            if layer.tau is None:
                raise ConfigError(f"{where}: unlocked level needs a tau")

    def _validate_tuned(
        self, where: str, locked: bool, model: ModelCfg, question_text: str
    ) -> None:
        if model.id is None:
            if not locked:
                raise ConfigError(f"{where}: tuned model has no id but the level is unlocked")
            return  # not trained yet, level is locked, nothing to serve
        if model.trained_question_sha256 is None:
            raise ConfigError(f"{where}: tuned model id set but trained_question_sha256 missing")
        if _sha256(question_text) != model.trained_question_sha256:
            raise ConfigError(
                f"{where}: question text does not match the tuned model's trained question hash"
            )

    def resolve_level(self, level: int) -> ResolvedLevel:
        if level not in self._raw.levels:
            raise ConfigError(f"unknown level {level}")
        cfg = self._raw.levels[level]
        layers: list[ResolvedLayer] = []
        for layer in cfg.layers:
            if layer.type == "rule_floor":
                layers.append(ResolvedLayer(layer.name, layer.type, None, None, None))
                continue
            model = self._model(layer.model, f"level {level} layer {layer.name!r}")
            question_text = self._question_text(
                layer.question, f"level {level} layer {layer.name!r}"
            )
            layers.append(ResolvedLayer(layer.name, layer.type, model.id, question_text, layer.tau))
        return ResolvedLevel(level=level, locked=cfg.locked, layers=tuple(layers))

    def usd_per_mtok(self, model_id: str) -> float:
        """Decision price for a model id. Unknown or unset prices use the highest
        published rate, so the budget guard errs toward pausing early."""
        for model in self._raw.models.values():
            if model.id == model_id and model.usd_per_mtok is not None:
                return model.usd_per_mtok
        return MAX_PUBLISHED_USD_PER_MTOK

    def resolve_verifier(self) -> ResolvedVerifier:
        model = self._model("V", "verifier")
        if model.id is None:
            raise ConfigError("verifier: model V has no id")
        if model.tau_verify is None:
            raise ConfigError("verifier: model V has no tau_verify")
        question_text = self._question_text(model.question, "verifier")
        return ResolvedVerifier(model.id, question_text, model.tau_verify)


def load_config(path: Path | None = None) -> GateConfig:
    """Load and validate gates.yaml. Raises ConfigError on any problem."""
    source = path or CONFIG_PATH
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"gates.yaml not found at {source}") from exc
    try:
        raw = GatesConfig.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - surface any schema error as a startup failure
        raise ConfigError(f"gates.yaml is invalid: {exc}") from exc
    return GateConfig(raw)
