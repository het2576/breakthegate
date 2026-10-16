"""Store contract tests, run against every implementation.

MemoryStore always runs. PostgresStore runs when TEST_DATABASE_URL is set: each
test gets a throwaway schema with the real migrations applied, dropped after.
Never point TEST_DATABASE_URL at production.
"""

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from psycopg import AsyncConnection

from app.store import UNSET, LevelProgress, MemoryStore, NewAttempt, Store
from app.store.migrate import apply_migrations
from app.store.postgres import PostgresStore

TEST_DB = os.environ.get("TEST_DATABASE_URL")
BACKENDS = ["memory"] + (["postgres"] if TEST_DB else [])


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(params=BACKENDS)
async def store(request: pytest.FixtureRequest) -> AsyncIterator[Store]:
    if request.param == "memory":
        yield MemoryStore()
        return
    assert TEST_DB is not None
    schema = f"t_{uuid.uuid4().hex[:12]}"
    async with await AsyncConnection.connect(TEST_DB, autocommit=True) as admin:
        await admin.execute(f'create schema "{schema}"'.encode())
    try:
        async with await AsyncConnection.connect(
            TEST_DB, options=f"-c search_path={schema}"
        ) as conn:
            await apply_migrations(conn)
        pg = await PostgresStore.connect(TEST_DB, options=f"-c search_path={schema}")
        try:
            yield pg
        finally:
            await pg.close()
    finally:
        async with await AsyncConnection.connect(TEST_DB, autocommit=True) as admin:
            await admin.execute(f'drop schema "{schema}" cascade'.encode())


pytestmark = pytest.mark.anyio


def _attempt(session_id: uuid.UUID, **overrides: Any) -> NewAttempt:
    fields: dict[str, Any] = {
        "session_id": session_id,
        "level": 1,
        "goal_id": 1,
        "task": "tidy",
        "command": "rm -rf /etc",
        "approved": False,
        "p_safe": 0.2,
        "threshold": 0.5,
        "deciding_layer": "model_a",
        "layers": [{"name": "model_a", "passed": False, "p_safe": 0.2, "detail": "x"}],
        "verified": True,
        "verify_p": 0.9,
        "verify_cache_hit": False,
        "points": 0,
        "gate_version": "v1",
        "latency_ms": 12,
        "consent_training": False,
    }
    fields.update(overrides)
    return NewAttempt(**fields)


async def test_session_lifecycle(store: Store) -> None:
    s = await store.create_session(handle="gatecrasher", consent_training=False, ip_hash="h")
    assert s.consent_training is False
    assert await store.get_session(s.id) == s

    updated = await store.update_session(s.id, consent_training=True)
    assert updated is not None and updated.consent_training and updated.handle == "gatecrasher"
    cleared = await store.update_session(s.id, handle=None)
    assert cleared is not None and cleared.handle is None and cleared.consent_training
    same = await store.update_session(s.id, handle=UNSET, consent_training=UNSET)
    assert same == cleared

    assert await store.get_session(uuid.uuid4()) is None
    assert await store.update_session(uuid.uuid4(), consent_training=True) is None


async def test_delete_removes_session_and_attempts(store: Store) -> None:
    s = await store.create_session(handle=None, consent_training=True, ip_hash=None)
    await store.insert_attempt(_attempt(s.id))
    assert await store.delete_session(s.id) is True
    assert await store.get_session(s.id) is None
    assert await store.list_attempts(s.id, level=None, limit=10, before=None) == []
    assert await store.delete_session(s.id) is False


async def test_attempt_roundtrip_and_paging(store: Store) -> None:
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    rows = [
        await store.insert_attempt(_attempt(s.id, goal_id=g, level=1 + g % 2)) for g in range(1, 6)
    ]
    page = await store.list_attempts(s.id, level=None, limit=3, before=None)
    assert [r.goal_id for r in page] == [5, 4, 3]  # newest first
    assert page[0].layers == rows[-1].layers
    rest = await store.list_attempts(s.id, level=None, limit=10, before=page[-1].created_at)
    assert {r.goal_id for r in rest} <= {1, 2}
    only_level_2 = await store.list_attempts(s.id, level=2, limit=10, before=None)
    assert {r.level for r in only_level_2} == {2}


async def test_has_win_on_goal_needs_approved_and_verified(store: Store) -> None:
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    await store.insert_attempt(_attempt(s.id, approved=True, verified=False))
    await store.insert_attempt(_attempt(s.id, approved=False, verified=True))
    assert await store.has_win_on_goal(s.id, 1, 1) is False
    await store.insert_attempt(_attempt(s.id, approved=True, verified=True, points=100))
    assert await store.has_win_on_goal(s.id, 1, 1) is True
    assert await store.has_win_on_goal(s.id, 1, 2) is False


async def test_reveal_is_unique_per_level_and_legendary_wins_need_review(store: Store) -> None:
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    attempt = await store.insert_attempt(
        _attempt(s.id, level=5, approved=True, verified=True, points=500)
    )
    reveal = await store.create_reveal(
        attempt_id=attempt.id,
        session_id=s.id,
        level=5,
        variant="legendary",
        needs_review=True,
    )
    assert reveal is not None and reveal.needs_review and reveal.variant == "legendary"
    assert (
        await store.create_reveal(
            attempt_id=attempt.id,
            session_id=s.id,
            level=5,
            variant="legendary",
            needs_review=True,
        )
        is None
    )
    claim = await store.claim_reveal(s.id, reveal.id)
    assert claim.status == "claimed" and claim.win is not None and claim.win.claimed
    assert (await store.claim_reveal(s.id, reveal.id)).status == "already_claimed"
    assert await store.list_wins(s.id) == [claim.win]
    assert await store.level_progress() == {5: LevelProgress(players_tried=1, winners=1)}


async def test_leaderboard_groups_by_session_and_orders(store: Store) -> None:
    a = await store.create_session(handle="same", consent_training=False, ip_hash=None)
    b = await store.create_session(handle="same", consent_training=False, ip_hash=None)
    c = await store.create_session(handle="carol", consent_training=False, ip_hash=None)
    anon = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    zero = await store.create_session(handle="zero", consent_training=False, ip_hash=None)

    await store.insert_attempt(_attempt(a.id, points=150, approved=True))  # 150 in 1
    await store.insert_attempt(_attempt(b.id))
    await store.insert_attempt(_attempt(b.id, points=150, approved=True))  # 150 in 2
    await store.insert_attempt(_attempt(c.id, points=200, approved=True))  # 200 in 1
    await store.insert_attempt(_attempt(anon.id, points=500, approved=True))  # no handle
    await store.insert_attempt(_attempt(zero.id))  # score 0: not listed
    await store.insert_attempt(_attempt(a.id, level=2, points=999, approved=True))  # other level

    board = await store.leaderboard(1, 50)
    assert [(r.handle, r.score, r.attempts) for r in board] == [
        ("carol", 200, 1),
        ("same", 150, 1),  # session a: fewer attempts first
        ("same", 150, 2),  # session b: same handle, separate row
    ]
    assert len(await store.leaderboard(1, 1)) == 1


async def test_latest_eval_empty(store: Store) -> None:
    assert await store.latest_eval() is None


async def test_idempotency_flow(store: Store) -> None:
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    assert (await store.claim_idempotency(s.id, "key-00000001", "h1")).status == "new"
    assert (await store.claim_idempotency(s.id, "key-00000001", "h1")).status == "in_progress"
    assert (await store.claim_idempotency(s.id, "key-00000001", "h2")).status == "reused"

    await store.complete_idempotency(s.id, "key-00000001", {"attempt_id": "x"})
    replay = await store.claim_idempotency(s.id, "key-00000001", "h1")
    assert replay.status == "replay" and replay.response == {"attempt_id": "x"}
    assert (await store.claim_idempotency(s.id, "key-00000001", "h2")).status == "reused"

    # A failed request releases its claim so the retry runs again.
    assert (await store.claim_idempotency(s.id, "key-00000002", "h1")).status == "new"
    await store.release_idempotency(s.id, "key-00000002")
    assert (await store.claim_idempotency(s.id, "key-00000002", "h1")).status == "new"


async def test_spend_accumulates_per_day(store: Store) -> None:
    today = date(2026, 10, 16)
    assert (await store.get_spend(today)).input_tokens == 0
    await store.add_spend(today, 100, 0.25)
    await store.add_spend(today, 50, 0.125)
    await store.add_spend(today + timedelta(days=1), 7, 1.0)
    spend = await store.get_spend(today)
    assert spend.input_tokens == 150
    assert spend.usd == pytest.approx(0.375)


# MemoryStore-only timing tests (Postgres uses the database clock).


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 16, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


async def test_idempotency_key_expires_after_ten_minutes() -> None:
    clock = Clock()
    store = MemoryStore(clock=clock)
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    await store.claim_idempotency(s.id, "key-00000001", "h1")
    await store.complete_idempotency(s.id, "key-00000001", {"a": 1})
    clock.now += timedelta(minutes=10)
    assert (await store.claim_idempotency(s.id, "key-00000001", "h2")).status == "new"


async def test_abandoned_in_progress_claim_is_taken_over() -> None:
    clock = Clock()
    store = MemoryStore(clock=clock)
    s = await store.create_session(handle=None, consent_training=False, ip_hash=None)
    await store.claim_idempotency(s.id, "key-00000001", "h1")
    clock.now += timedelta(seconds=59)
    assert (await store.claim_idempotency(s.id, "key-00000001", "h1")).status == "in_progress"
    clock.now += timedelta(seconds=1)
    assert (await store.claim_idempotency(s.id, "key-00000001", "h1")).status == "new"
