"""Runtime settings from the environment (docs/PRD.md section 13).

APP_ENV=prod refuses to start without the security-critical values, so a missing
secret fails the deploy instead of silently weakening the gate.
"""

import os
from dataclasses import dataclass
from typing import Literal

EndorMode = Literal["mock", "live"]
AppEnv = Literal["dev", "prod"]

DEV_PROXY_SECRET = "dev-proxy-secret"  # noqa: S105 - dev placeholder, rejected in prod
DEV_SALT_SEED = "dev-salt-seed"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _str(name: str) -> str | None:
    raw = os.environ.get(name, "").strip()
    return raw or None


@dataclass(frozen=True)
class Settings:
    app_env: AppEnv = "dev"
    endor_mode: EndorMode = "mock"
    endor_api_key: str | None = None  # never logged, never sent to the browser
    database_url: str | None = None  # None: in-memory store (dev only)
    proxy_secret: str = DEV_PROXY_SECRET
    ip_hash_salt_seed: str = DEV_SALT_SEED
    warm_secret: str | None = None  # None: /health/warm is disabled
    reveal_video_id: str | None = None  # returned only after a successful reveal claim
    turnstile_secret: str | None = None  # None: session creation skips the human check
    game_paused: bool = False
    max_daily_usd: float = 5.0
    max_daily_tokens: int = 5_000_000
    rate_session_per_hour: int = 60
    rate_ip_per_hour: int = 120
    cookie_secure: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        env = (os.environ.get("APP_ENV", "dev").strip().lower()) or "dev"
        if env not in ("dev", "prod"):
            raise ValueError(f"APP_ENV must be 'dev' or 'prod', got {env!r}")
        mode = os.environ.get("ENDOR_MODE", "mock").strip().lower()
        if mode not in ("mock", "live"):
            raise ValueError(f"ENDOR_MODE must be 'mock' or 'live', got {mode!r}")
        prod = env == "prod"
        settings = cls(
            app_env="prod" if prod else "dev",
            endor_mode="live" if mode == "live" else "mock",
            endor_api_key=_str("ENDOR_API_KEY"),
            database_url=_str("DATABASE_URL"),
            proxy_secret=_str("PROXY_SECRET") or DEV_PROXY_SECRET,
            ip_hash_salt_seed=_str("IP_HASH_SALT_SEED") or DEV_SALT_SEED,
            warm_secret=_str("WARM_SECRET"),
            reveal_video_id=_str("REVEAL_VIDEO_ID"),
            turnstile_secret=_str("TURNSTILE_SECRET"),
            game_paused=_bool("GAME_PAUSED", False),
            max_daily_usd=float(os.environ.get("MAX_DAILY_USD", "5") or 5),
            max_daily_tokens=int(os.environ.get("MAX_DAILY_TOKENS", "5000000") or 5_000_000),
            cookie_secure=_bool("COOKIE_SECURE", prod),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.endor_mode == "live" and not self.endor_api_key:
            raise ValueError("ENDOR_MODE=live needs ENDOR_API_KEY")
        if self.app_env != "prod":
            return
        problems: list[str] = []
        if not self.database_url:
            problems.append("DATABASE_URL is required")
        if self.proxy_secret == DEV_PROXY_SECRET or len(self.proxy_secret) < 32:
            problems.append("PROXY_SECRET must be set to a random value of 32+ characters")
        if self.ip_hash_salt_seed == DEV_SALT_SEED or len(self.ip_hash_salt_seed) < 32:
            problems.append("IP_HASH_SALT_SEED must be set to a random value of 32+ characters")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if problems:
            raise ValueError("invalid production settings: " + "; ".join(problems))

    def __repr__(self) -> str:  # keep secrets out of tracebacks and logs
        return (
            f"Settings(app_env={self.app_env!r}, endor_mode={self.endor_mode!r}, "
            f"endor_api_key={'set' if self.endor_api_key else None}, "
            f"database_url={'set' if self.database_url else None}, game_paused={self.game_paused})"
        )
