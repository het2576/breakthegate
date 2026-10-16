"""Storage interface and row types (docs/PRD.md section 8).

Two implementations share this contract and one test suite: MemoryStore (tests,
local dev without a database) and PostgresStore (Supabase in production).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Literal, Protocol
from uuid import UUID

IDEMPOTENCY_TTL_S = 600.0  # keys live 10 minutes (PRD 6.6)
IDEMPOTENCY_ABANDON_S = 60.0  # an in-progress claim older than this is abandoned
REVEAL_TTL = timedelta(minutes=10)


class Unset(Enum):
    """Sentinel for "leave this field alone" in partial updates."""

    TOKEN = 0


UNSET = Unset.TOKEN


@dataclass(frozen=True)
class SessionRow:
    id: UUID
    handle: str | None
    consent_training: bool
    created_at: datetime


@dataclass(frozen=True)
class NewAttempt:
    session_id: UUID
    level: int
    goal_id: int
    task: str
    command: str
    approved: bool
    p_safe: float
    threshold: float
    deciding_layer: str
    layers: list[dict[str, Any]]
    verified: bool | None
    verify_p: float | None
    verify_cache_hit: bool
    points: int
    gate_version: str
    latency_ms: int | None
    consent_training: bool


@dataclass(frozen=True)
class AttemptRow:
    id: UUID
    created_at: datetime
    session_id: UUID
    level: int
    goal_id: int
    task: str
    command: str
    approved: bool
    p_safe: float
    threshold: float
    deciding_layer: str
    layers: list[dict[str, Any]]
    verified: bool | None
    verify_p: float | None
    points: int
    gate_version: str


@dataclass(frozen=True)
class LeaderboardRow:
    handle: str
    score: int
    attempts: int


@dataclass(frozen=True)
class RevealRow:
    id: UUID
    attempt_id: UUID
    session_id: UUID
    level: int
    variant: Literal["standard", "legendary"]
    expires_at: datetime
    claimed_at: datetime | None
    needs_review: bool
    created_at: datetime


@dataclass(frozen=True)
class WinRow:
    level: int
    variant: Literal["standard", "legendary"]
    attempts: int
    seconds: int
    claimed: bool


RevealClaimStatus = Literal["claimed", "not_found", "already_claimed", "expired"]


@dataclass(frozen=True)
class RevealClaim:
    status: RevealClaimStatus
    win: WinRow | None = None


@dataclass(frozen=True)
class LevelProgress:
    players_tried: int
    winners: int


@dataclass(frozen=True)
class Spend:
    input_tokens: int
    usd: float


ClaimStatus = Literal["new", "replay", "reused", "in_progress"]


@dataclass(frozen=True)
class IdempotencyClaim:
    status: ClaimStatus
    response: dict[str, Any] | None = None  # set for "replay"


class Store(Protocol):
    # sessions
    async def create_session(
        self, *, handle: str | None, consent_training: bool, ip_hash: str | None
    ) -> SessionRow: ...

    async def get_session(self, session_id: UUID) -> SessionRow | None: ...

    async def update_session(
        self,
        session_id: UUID,
        *,
        handle: str | None | Unset = UNSET,
        consent_training: bool | Unset = UNSET,
    ) -> SessionRow | None: ...

    async def delete_session(self, session_id: UUID) -> bool:
        """Remove the session and, by cascade, every attempt, reveal and key."""
        ...

    # attempts
    async def insert_attempt(self, attempt: NewAttempt) -> AttemptRow: ...

    async def list_attempts(
        self, session_id: UUID, *, level: int | None, limit: int, before: datetime | None
    ) -> list[AttemptRow]:
        """Newest first. `before` is an exclusive created_at cursor for paging."""
        ...

    async def has_win_on_goal(self, session_id: UUID, level: int, goal_id: int) -> bool:
        """Whether this session already has an approved and verified attempt for the goal."""
        ...

    async def leaderboard(self, level: int, limit: int) -> list[LeaderboardRow]:
        """Sessions with a handle and a positive score: score desc, attempts asc, first win asc."""
        ...

    # reveals (PRD 3.7, 7)
    async def create_reveal(
        self,
        *,
        attempt_id: UUID,
        session_id: UUID,
        level: int,
        variant: Literal["standard", "legendary"],
        needs_review: bool,
    ) -> RevealRow | None:
        """Issue a reveal once per session and level, or return None for a repeat win."""
        ...

    async def claim_reveal(self, session_id: UUID, reveal_id: UUID) -> RevealClaim:
        """Atomically claim a reveal, keeping unknown and other-session ids indistinguishable."""
        ...

    async def list_wins(self, session_id: UUID) -> list[WinRow]:
        """Own wins and badges only. Never includes task or command text."""
        ...

    async def level_progress(self) -> dict[int, LevelProgress]:
        """Unique players who tried and won each level, for sealed-vault teasers."""
        ...

    # report
    async def latest_eval(self) -> dict[str, Any] | None: ...

    # idempotency (PRD 6.6)
    async def claim_idempotency(
        self, session_id: UUID, key: str, request_hash: str
    ) -> IdempotencyClaim: ...

    async def complete_idempotency(
        self, session_id: UUID, key: str, response: dict[str, Any]
    ) -> None: ...

    async def release_idempotency(self, session_id: UUID, key: str) -> None:
        """Forget an in-progress claim whose request failed, so a retry runs again."""
        ...

    # budget (PRD 4.3)
    async def add_spend(self, day: date, input_tokens: int, usd: float) -> None: ...

    async def get_spend(self, day: date) -> Spend: ...

    async def close(self) -> None: ...
