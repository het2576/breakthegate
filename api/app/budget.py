"""Daily spend guard (docs/PRD.md 4.3). Checked before any decision call.

Spend is estimated from token counts and configured prices, persisted per UTC day
in the store so restarts do not reset it. Cache hits cost nothing.
"""

from datetime import UTC, date, datetime

from app.gate.config import GateConfig
from app.gate.types import GateDecision, VerifyResult
from app.store import Store


def utc_today() -> date:
    return datetime.now(UTC).date()


class Budget:
    def __init__(
        self, store: Store, config: GateConfig, *, max_usd: float, max_tokens: int
    ) -> None:
        self._store = store
        self._config = config
        self._max_usd = max_usd
        self._max_tokens = max_tokens

    async def exhausted(self, day: date) -> bool:
        spend = await self._store.get_spend(day)
        return spend.usd >= self._max_usd or spend.input_tokens >= self._max_tokens

    def cost(self, level: int, gate: GateDecision, verify: VerifyResult) -> tuple[int, float]:
        """(input tokens, USD) for one attempt's calls."""
        model_by_layer = {
            layer.name: layer.model_id for layer in self._config.resolve_level(level).layers
        }
        tokens = 0
        usd = 0.0
        for layer in gate.layers:
            model_id = model_by_layer.get(layer.name)
            if model_id is None or layer.input_tokens == 0:
                continue
            tokens += layer.input_tokens
            usd += layer.input_tokens * self._config.usd_per_mtok(model_id) / 1_000_000
        if verify.input_tokens:
            verifier_id = self._config.resolve_verifier().model_id
            tokens += verify.input_tokens
            usd += verify.input_tokens * self._config.usd_per_mtok(verifier_id) / 1_000_000
        return tokens, usd

    async def record(self, day: date, level: int, gate: GateDecision, verify: VerifyResult) -> None:
        tokens, usd = self.cost(level, gate, verify)
        if tokens:
            await self._store.add_spend(day, tokens, usd)
