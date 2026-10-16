"""Postgres Store (Supabase in production), on psycopg 3 with a connection pool.

Every query is parameterized; no SQL is built from user text. Prepared statements
are disabled (prepare_threshold=None) so the store also works through Supabase's
transaction pooler. Times come from the database clock, so several API instances
agree on idempotency windows.
"""

from datetime import date, datetime
from typing import Any, Literal, LiteralString
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.store.base import (
    IDEMPOTENCY_ABANDON_S,
    IDEMPOTENCY_TTL_S,
    UNSET,
    AttemptRow,
    IdempotencyClaim,
    LeaderboardRow,
    LevelProgress,
    NewAttempt,
    RevealClaim,
    RevealRow,
    SessionRow,
    Spend,
    Unset,
    WinRow,
)


def _session(row: DictRow) -> SessionRow:
    return SessionRow(row["id"], row["handle"], row["consent_training"], row["created_at"])


def _attempt(row: DictRow) -> AttemptRow:
    return AttemptRow(
        id=row["id"],
        created_at=row["created_at"],
        session_id=row["session_id"],
        level=row["level"],
        goal_id=row["goal_id"],
        task=row["task"],
        command=row["command"],
        approved=row["approved"],
        p_safe=row["p_safe"],
        threshold=row["threshold"],
        deciding_layer=row["deciding_layer"],
        layers=row["layers"],
        verified=row["verified"],
        verify_p=row["verify_p"],
        points=row["points"],
        gate_version=row["gate_version"],
    )


def _reveal(row: DictRow) -> RevealRow:
    return RevealRow(
        id=row["id"],
        attempt_id=row["attempt_id"],
        session_id=row["session_id"],
        level=row["level"],
        variant=row["variant"],  # pyright: ignore[reportArgumentType]
        expires_at=row["expires_at"],
        claimed_at=row["claimed_at"],
        needs_review=row["needs_review"],
        created_at=row["created_at"],
    )


class PostgresStore:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[DictRow]]) -> None:
        self._pool = pool

    @classmethod
    async def connect(
        cls, conninfo: str, *, min_size: int = 1, max_size: int = 5, options: str | None = None
    ) -> "PostgresStore":
        kwargs: dict[str, Any] = {"prepare_threshold": None, "row_factory": dict_row}
        if options:
            kwargs["options"] = options  # tests pin search_path to a throwaway schema
        pool = AsyncConnectionPool(
            conninfo,
            min_size=min_size,
            max_size=max_size,
            kwargs=kwargs,
            connection_class=AsyncConnection[DictRow],
            open=False,
        )
        await pool.open(wait=True)
        return cls(pool)

    async def _one(self, sql: LiteralString, params: tuple[Any, ...]) -> DictRow | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()

    async def _all(self, sql: LiteralString, params: tuple[Any, ...]) -> list[DictRow]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()

    # sessions -------------------------------------------------------------

    async def create_session(
        self, *, handle: str | None, consent_training: bool, ip_hash: str | None
    ) -> SessionRow:
        row = await self._one(
            "insert into sessions (handle, consent_training, ip_hash) values (%s, %s, %s) "
            "returning id, handle, consent_training, created_at",
            (handle, consent_training, ip_hash),
        )
        assert row is not None  # noqa: S101 - insert ... returning always yields a row
        return _session(row)

    async def get_session(self, session_id: UUID) -> SessionRow | None:
        row = await self._one(
            "select id, handle, consent_training, created_at from sessions "
            "where id = %s and deleted_at is null",
            (session_id,),
        )
        return _session(row) if row else None

    async def update_session(
        self,
        session_id: UUID,
        *,
        handle: str | None | Unset = UNSET,
        consent_training: bool | Unset = UNSET,
    ) -> SessionRow | None:
        set_handle = not isinstance(handle, Unset)
        set_consent = not isinstance(consent_training, Unset)
        row = await self._one(
            "update sessions set "
            "handle = case when %s then %s else handle end, "
            "consent_training = case when %s then %s else consent_training end "
            "where id = %s and deleted_at is null "
            "returning id, handle, consent_training, created_at",
            (
                set_handle,
                None if isinstance(handle, Unset) else handle,
                set_consent,
                False if isinstance(consent_training, Unset) else consent_training,
                session_id,
            ),
        )
        return _session(row) if row else None

    async def delete_session(self, session_id: UUID) -> bool:
        row = await self._one("delete from sessions where id = %s returning id", (session_id,))
        return row is not None

    # attempts -------------------------------------------------------------

    async def insert_attempt(self, attempt: NewAttempt) -> AttemptRow:
        row = await self._one(
            "insert into attempts (session_id, level, goal_id, task, command, approved, p_safe, "
            "threshold, deciding_layer, layers, verified, verify_p, verify_cache_hit, points, "
            "gate_version, latency_ms, consent_training) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "returning id, created_at, session_id, level, goal_id, task, command, approved, "
            "p_safe, threshold, deciding_layer, layers, verified, verify_p, points, gate_version",
            (
                attempt.session_id,
                attempt.level,
                attempt.goal_id,
                attempt.task,
                attempt.command,
                attempt.approved,
                attempt.p_safe,
                attempt.threshold,
                attempt.deciding_layer,
                Jsonb(attempt.layers),
                attempt.verified,
                attempt.verify_p,
                attempt.verify_cache_hit,
                attempt.points,
                attempt.gate_version,
                attempt.latency_ms,
                attempt.consent_training,
            ),
        )
        assert row is not None  # noqa: S101 - insert ... returning always yields a row
        return _attempt(row)

    async def list_attempts(
        self, session_id: UUID, *, level: int | None, limit: int, before: datetime | None
    ) -> list[AttemptRow]:
        rows = await self._all(
            "select id, created_at, session_id, level, goal_id, task, command, approved, p_safe, "
            "threshold, deciding_layer, layers, verified, verify_p, points, gate_version "
            "from attempts where session_id = %s "
            "and (%s::smallint is null or level = %s) "
            "and (%s::timestamptz is null or created_at < %s) "
            "order by created_at desc limit %s",
            (session_id, level, level, before, before, limit),
        )
        return [_attempt(r) for r in rows]

    async def has_win_on_goal(self, session_id: UUID, level: int, goal_id: int) -> bool:
        row = await self._one(
            "select exists (select 1 from attempts where session_id = %s and level = %s "
            "and goal_id = %s and approved and verified) as won",
            (session_id, level, goal_id),
        )
        return bool(row and row["won"])

    async def leaderboard(self, level: int, limit: int) -> list[LeaderboardRow]:
        rows = await self._all(
            "select handle, score, attempts from leaderboard where level = %s and score > 0 "
            "order by score desc, attempts asc, first_win_at asc nulls last limit %s",
            (level, limit),
        )
        return [LeaderboardRow(r["handle"], int(r["score"]), int(r["attempts"])) for r in rows]

    # reveals --------------------------------------------------------------

    async def create_reveal(
        self,
        *,
        attempt_id: UUID,
        session_id: UUID,
        level: int,
        variant: Literal["standard", "legendary"],
        needs_review: bool,
    ) -> RevealRow | None:
        row = await self._one(
            "insert into reveals (attempt_id, session_id, level, variant, expires_at, "
            "needs_review) "
            "values (%s, %s, %s, %s, now() + interval '10 minutes', %s) "
            "on conflict (session_id, level) do nothing "
            "returning id, attempt_id, session_id, level, variant, expires_at, claimed_at, "
            "needs_review, created_at",
            (attempt_id, session_id, level, variant, needs_review),
        )
        return _reveal(row) if row else None

    @staticmethod
    def _win(row: DictRow, *, claimed: bool) -> WinRow:
        return WinRow(
            level=row["level"],
            variant=row["variant"],  # pyright: ignore[reportArgumentType]
            attempts=int(row["attempts"]),
            seconds=max(0, int(row["seconds"])),
            claimed=claimed,
        )

    async def claim_reveal(self, session_id: UUID, reveal_id: UUID) -> RevealClaim:
        async with self._pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "select r.id, r.level, r.variant, r.expires_at, r.claimed_at, "
                    "a.created_at as attempt_created_at, s.created_at as session_created_at "
                    "from reveals r join attempts a on a.id = r.attempt_id "
                    "join sessions s on s.id = r.session_id "
                    "where r.id = %s and r.session_id = %s for update",
                    (reveal_id, session_id),
                )
            ).fetchone()
            if row is None:
                return RevealClaim("not_found")
            if row["claimed_at"] is not None:
                return RevealClaim("already_claimed")
            now = await (await conn.execute("select now() as now", ())).fetchone()
            assert now is not None  # noqa: S101 - select now() returns one row
            if now["now"] >= row["expires_at"]:
                return RevealClaim("expired")
            await conn.execute("update reveals set claimed_at = now() where id = %s", (reveal_id,))
            stats = await (
                await conn.execute(
                    "select count(*) as attempts, "
                    "extract(epoch from %s::timestamptz - %s::timestamptz) as seconds "
                    "from attempts where session_id = %s and level = %s and created_at <= %s",
                    (
                        row["attempt_created_at"],
                        row["session_created_at"],
                        session_id,
                        row["level"],
                        row["attempt_created_at"],
                    ),
                )
            ).fetchone()
            assert stats is not None  # noqa: S101 - aggregate query returns one row
            return RevealClaim(
                "claimed",
                WinRow(
                    level=row["level"],
                    variant=row["variant"],  # pyright: ignore[reportArgumentType]
                    attempts=int(stats["attempts"]),
                    seconds=max(0, int(stats["seconds"])),
                    claimed=True,
                ),
            )

    async def list_wins(self, session_id: UUID) -> list[WinRow]:
        rows = await self._all(
            "select r.level, r.variant, r.claimed_at is not null as claimed, "
            "count(a.id) as attempts, "
            "extract(epoch from win.created_at - s.created_at) as seconds "
            "from reveals r join attempts win on win.id = r.attempt_id "
            "join sessions s on s.id = r.session_id "
            "join attempts a on a.session_id = r.session_id and a.level = r.level "
            "and a.created_at <= win.created_at "
            "where r.session_id = %s "
            "group by r.id, r.level, r.variant, r.claimed_at, win.created_at, s.created_at "
            "order by r.level asc",
            (session_id,),
        )
        return [self._win(row, claimed=bool(row["claimed"])) for row in rows]

    async def level_progress(self) -> dict[int, LevelProgress]:
        rows = await self._all(
            "select level, count(distinct session_id) as players_tried, "
            "count(distinct session_id) filter (where approved and verified) as winners "
            "from attempts group by level",
            (),
        )
        return {
            row["level"]: LevelProgress(int(row["players_tried"]), int(row["winners"]))
            for row in rows
        }

    # report ---------------------------------------------------------------

    async def latest_eval(self) -> dict[str, Any] | None:
        row = await self._one("select payload from evals order by created_at desc limit 1", ())
        return row["payload"] if row else None

    # idempotency ----------------------------------------------------------

    async def claim_idempotency(
        self, session_id: UUID, key: str, request_hash: str
    ) -> IdempotencyClaim:
        async with self._pool.connection() as conn, conn.transaction():
            inserted = await (
                await conn.execute(
                    "insert into idempotency_keys (session_id, key, request_hash) "
                    "values (%s, %s, %s) on conflict (session_id, key) do nothing returning key",
                    (session_id, key, request_hash),
                )
            ).fetchone()
            if inserted is not None:
                return IdempotencyClaim("new")

            row = await (
                await conn.execute(
                    "select request_hash, status, response, "
                    "extract(epoch from now() - created_at) as age_s "
                    "from idempotency_keys where session_id = %s and key = %s for update",
                    (session_id, key),
                )
            ).fetchone()
            if row is None:  # deleted between the two statements: treat as new next time
                return IdempotencyClaim("in_progress")

            age_s = float(row["age_s"])
            restart = (
                "update idempotency_keys set request_hash = %s, status = 'in_progress', "
                "response = null, created_at = now() where session_id = %s and key = %s"
            )
            if age_s >= IDEMPOTENCY_TTL_S:
                await conn.execute(restart, (request_hash, session_id, key))
                return IdempotencyClaim("new")
            if row["request_hash"] != request_hash:
                return IdempotencyClaim("reused")
            if row["status"] == "done":
                return IdempotencyClaim("replay", row["response"])
            if age_s >= IDEMPOTENCY_ABANDON_S:
                await conn.execute(restart, (request_hash, session_id, key))
                return IdempotencyClaim("new")
            return IdempotencyClaim("in_progress")

    async def complete_idempotency(
        self, session_id: UUID, key: str, response: dict[str, Any]
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "update idempotency_keys set status = 'done', response = %s "
                "where session_id = %s and key = %s",
                (Jsonb(response), session_id, key),
            )

    async def release_idempotency(self, session_id: UUID, key: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "delete from idempotency_keys where session_id = %s and key = %s "
                "and status = 'in_progress'",
                (session_id, key),
            )

    # budget ---------------------------------------------------------------

    async def add_spend(self, day: date, input_tokens: int, usd: float) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "insert into spend_daily (day, input_tokens, usd) values (%s, %s, %s) "
                "on conflict (day) do update set "
                "input_tokens = spend_daily.input_tokens + excluded.input_tokens, "
                "usd = spend_daily.usd + excluded.usd",
                (day, input_tokens, usd),
            )

    async def get_spend(self, day: date) -> Spend:
        row = await self._one("select input_tokens, usd from spend_daily where day = %s", (day,))
        if row is None:
            return Spend(0, 0.0)
        return Spend(int(row["input_tokens"]), float(row["usd"]))

    async def close(self) -> None:
        await self._pool.close()
