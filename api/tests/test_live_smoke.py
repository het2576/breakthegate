"""Live smoke test (PRD 12.4). Skipped by default; run manually:

    ENDOR_API_KEY=edk_... ENDOR_SMOKE_MODEL=<project>/<base id> uv run pytest -m live -s

Makes one real, billed decision and prints its latency.
"""

import asyncio
import os
import time

import pytest

from app.endor_client import LiveEndor

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not (os.environ.get("ENDOR_API_KEY") and os.environ.get("ENDOR_SMOKE_MODEL")),
    reason="needs ENDOR_API_KEY and ENDOR_SMOKE_MODEL",
)
def test_one_real_decision() -> None:
    async def go() -> tuple[float, float]:
        client = LiveEndor(os.environ["ENDOR_API_KEY"])
        try:
            started = time.perf_counter()
            decision = await client.decide(
                os.environ["ENDOR_SMOKE_MODEL"],
                {"task": "list files", "command": "ls -la"},
                'Is it safe for an automated coding agent to run the command in "command"?',
            )
            return decision.p, time.perf_counter() - started
        finally:
            await client.aclose()

    p, seconds = asyncio.run(go())
    print(f"\nlive decision p_safe={p:.3f} latency={seconds * 1000:.0f}ms")
    assert 0.0 <= p <= 1.0
