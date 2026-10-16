"""In-memory Store for tests and local dev without a database.

Mirrors PostgresStore's semantics (cascade delete, leaderboard order, idempotency
rules) and runs the same contract tests. Not for production: data is lost on
restart and not shared across processes.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from app.store.base import (
    IDEMPOTENCY_ABANDON_S,
    IDEMPOTENCY_TTL_S,
    REVEAL_TTL,
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


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Key:
    request_hash: str
    status: str  # in_progress | done
    response: dict[str, Any] | None
    created_at: datetime


@dataclass
class _Reveal:
    row: RevealRow
    attempt_seq: int


class MemoryStore:
    def __init__(self, *, clock: Callable[[], datetime] = _utcnow) -> None:
        self._clock = clock
        self._sessions: dict[UUID, SessionRow] = {}
        self._attempts: list[tuple[int, AttemptRow, NewAttempt]] = []  # (seq, row, input)
        self._seq = 0
        self._keys: dict[tuple[UUID, str], _Key] = {}
        self._reveals: dict[UUID, _Reveal] = {}
        self._spend: dict[date, Spend] = {}
        self.evals: list[dict[str, Any]] = []  # tests append payloads, newest last

    # sessions -------------------------------------------------------------

    async def create_session(
        self, *, handle: str | None, consent_training: bool, ip_hash: str | None
    ) -> SessionRow:
        row = SessionRow(uuid.uuid4(), handle, consent_training, self._clock())
        self._sessions[row.id] = row
        return row

    async def get_session(self, session_id: UUID) -> SessionRow | None:
        return self._sessions.get(session_id)

    async def update_session(
        self,
        session_id: UUID,
        *,
        handle: str | None | Unset = UNSET,
        consent_training: bool | Unset = UNSET,
    ) -> SessionRow | None:
        row = self._sessions.get(session_id)
        if row is None:
            return None
        if not isinstance(handle, Unset):
            row = replace(row, handle=handle)
        if not isinstance(consent_training, Unset):
            row = replace(row, consent_training=consent_training)
        self._sessions[session_id] = row
        return row

    async def delete_session(self, session_id: UUID) -> bool:
        if self._sessions.pop(session_id, None) is None:
            return False
        self._attempts = [a for a in self._attempts if a[1].session_id != session_id]
        self._keys = {k: v for k, v in self._keys.items() if k[0] != session_id}
        self._reveals = {
            reveal_id: reveal
            for reveal_id, reveal in self._reveals.items()
            if reveal.row.session_id != session_id
        }
        return True

    # attempts -------------------------------------------------------------

    async def insert_attempt(self, attempt: NewAttempt) -> AttemptRow:
        if attempt.session_id not in self._sessions:
            raise KeyError("unknown session")  # mirrors the foreign key
        self._seq += 1
        row = AttemptRow(
            id=uuid.uuid4(),
            created_at=self._clock(),
            session_id=attempt.session_id,
            level=attempt.level,
            goal_id=attempt.goal_id,
            task=attempt.task,
            command=attempt.command,
            approved=attempt.approved,
            p_safe=attempt.p_safe,
            threshold=attempt.threshold,
            deciding_layer=attempt.deciding_layer,
            layers=attempt.layers,
            verified=attempt.verified,
            verify_p=attempt.verify_p,
            points=attempt.points,
            gate_version=attempt.gate_version,
        )
        self._attempts.append((self._seq, row, attempt))
        return row

    async def list_attempts(
        self, session_id: UUID, *, level: int | None, limit: int, before: datetime | None
    ) -> list[AttemptRow]:
        rows = [
            (seq, row)
            for seq, row, _ in self._attempts
            if row.session_id == session_id
            and (level is None or row.level == level)
            and (before is None or row.created_at < before)
        ]
        rows.sort(key=lambda item: (item[1].created_at, item[0]), reverse=True)
        return [row for _, row in rows[:limit]]

    async def has_win_on_goal(self, session_id: UUID, level: int, goal_id: int) -> bool:
        return any(
            row.session_id == session_id
            and row.level == level
            and row.goal_id == goal_id
            and row.approved
            and row.verified is True
            for _, row, _ in self._attempts
        )

    async def leaderboard(self, level: int, limit: int) -> list[LeaderboardRow]:
        groups: dict[UUID, tuple[int, int, datetime | None]] = {}
        for _, row, _ in self._attempts:
            session = self._sessions.get(row.session_id)
            if row.level != level or session is None or session.handle is None:
                continue
            score, count, first_win = groups.get(row.session_id, (0, 0, None))
            if row.points > 0 and (first_win is None or row.created_at < first_win):
                first_win = row.created_at
            groups[row.session_id] = (score + row.points, count + 1, first_win)

        far_future = datetime.max.replace(tzinfo=UTC)
        ranked = sorted(
            ((sid, *values) for sid, values in groups.items() if values[0] > 0),
            key=lambda g: (-g[1], g[2], g[3] or far_future),
        )
        return [
            LeaderboardRow(handle=self._sessions[sid].handle or "", score=score, attempts=count)
            for sid, score, count, _ in ranked[:limit]
        ]

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
        if any(
            reveal.row.session_id == session_id and reveal.row.level == level
            for reveal in self._reveals.values()
        ):
            return None
        attempt = next(
            ((seq, row) for seq, row, _ in self._attempts if row.id == attempt_id),
            None,
        )
        if attempt is None or attempt[1].session_id != session_id:
            raise KeyError("unknown attempt")
        now = self._clock()
        row = RevealRow(
            id=uuid.uuid4(),
            attempt_id=attempt_id,
            session_id=session_id,
            level=level,
            variant=variant,
            expires_at=now + REVEAL_TTL,
            claimed_at=None,
            needs_review=needs_review,
            created_at=now,
        )
        self._reveals[row.id] = _Reveal(row=row, attempt_seq=attempt[0])
        return row

    def _win(self, reveal: _Reveal) -> WinRow:
        row = reveal.row
        session = self._sessions[row.session_id]
        attempts = sum(
            1
            for seq, attempt, _ in self._attempts
            if attempt.session_id == row.session_id
            and attempt.level == row.level
            and seq <= reveal.attempt_seq
        )
        seconds = max(0, int((row.created_at - session.created_at).total_seconds()))
        return WinRow(row.level, row.variant, attempts, seconds, row.claimed_at is not None)

    async def claim_reveal(self, session_id: UUID, reveal_id: UUID) -> RevealClaim:
        reveal = self._reveals.get(reveal_id)
        if reveal is None or reveal.row.session_id != session_id:
            return RevealClaim("not_found")
        if reveal.row.claimed_at is not None:
            return RevealClaim("already_claimed")
        if self._clock() >= reveal.row.expires_at:
            return RevealClaim("expired")
        reveal.row = replace(reveal.row, claimed_at=self._clock())
        return RevealClaim("claimed", self._win(reveal))

    async def list_wins(self, session_id: UUID) -> list[WinRow]:
        wins = [
            self._win(reveal)
            for reveal in self._reveals.values()
            if reveal.row.session_id == session_id
        ]
        return sorted(wins, key=lambda win: win.level)

    async def level_progress(self) -> dict[int, LevelProgress]:
        progress: dict[int, tuple[set[UUID], set[UUID]]] = {}
        for _, row, _ in self._attempts:
            tried, winners = progress.setdefault(row.level, (set(), set()))
            tried.add(row.session_id)
            if row.approved and row.verified is True:
                winners.add(row.session_id)
        return {
            level: LevelProgress(players_tried=len(tried), winners=len(winners))
            for level, (tried, winners) in progress.items()
        }

    # report ---------------------------------------------------------------

    async def latest_eval(self) -> dict[str, Any] | None:
        return self.evals[-1] if self.evals else None

    # idempotency ----------------------------------------------------------

    async def claim_idempotency(
        self, session_id: UUID, key: str, request_hash: str
    ) -> IdempotencyClaim:
        now = self._clock()
        existing = self._keys.get((session_id, key))
        fresh = _Key(request_hash, "in_progress", None, now)
        if existing is None or now - existing.created_at >= timedelta(seconds=IDEMPOTENCY_TTL_S):
            self._keys[(session_id, key)] = fresh
            return IdempotencyClaim("new")
        if existing.request_hash != request_hash:
            return IdempotencyClaim("reused")
        if existing.status == "done":
            return IdempotencyClaim("replay", existing.response)
        if now - existing.created_at >= timedelta(seconds=IDEMPOTENCY_ABANDON_S):
            self._keys[(session_id, key)] = fresh
            return IdempotencyClaim("new")
        return IdempotencyClaim("in_progress")

    async def complete_idempotency(
        self, session_id: UUID, key: str, response: dict[str, Any]
    ) -> None:
        existing = self._keys.get((session_id, key))
        if existing is not None:
            existing.status = "done"
            existing.response = response

    async def release_idempotency(self, session_id: UUID, key: str) -> None:
        existing = self._keys.get((session_id, key))
        if existing is not None and existing.status == "in_progress":
            del self._keys[(session_id, key)]

    # budget ---------------------------------------------------------------

    async def add_spend(self, day: date, input_tokens: int, usd: float) -> None:
        current = self._spend.get(day, Spend(0, 0.0))
        self._spend[day] = Spend(current.input_tokens + input_tokens, current.usd + usd)

    async def get_spend(self, day: date) -> Spend:
        return self._spend.get(day, Spend(0, 0.0))

    async def close(self) -> None:
        return None
