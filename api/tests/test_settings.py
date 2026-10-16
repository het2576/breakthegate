"""Settings tests: ENDOR_MODE parsing and key handling."""

import pytest

from app.settings import Settings


def test_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENDOR_MODE", raising=False)
    monkeypatch.delenv("ENDOR_API_KEY", raising=False)
    assert Settings.from_env() == Settings(endor_mode="mock", endor_api_key=None)


def test_reads_live_mode_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENDOR_MODE", " Live ")
    monkeypatch.setenv("ENDOR_API_KEY", "edk_x")
    assert Settings.from_env() == Settings(endor_mode="live", endor_api_key="edk_x")


def test_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENDOR_MODE", "prod")
    with pytest.raises(ValueError, match="ENDOR_MODE"):
        Settings.from_env()


GOOD_PROD = {
    "APP_ENV": "prod",
    "DATABASE_URL": "postgresql://u:p@db.example.test:5432/postgres",
    "PROXY_SECRET": "p" * 40,
    "IP_HASH_SALT_SEED": "s" * 40,
}


def _env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for name in (
        "APP_ENV",
        "DATABASE_URL",
        "PROXY_SECRET",
        "IP_HASH_SALT_SEED",
        "COOKIE_SECURE",
        "ENDOR_MODE",
        "ENDOR_API_KEY",
        "GAME_PAUSED",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_prod_with_everything_set_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, GOOD_PROD)
    settings = Settings.from_env()
    assert settings.app_env == "prod" and settings.cookie_secure is True


@pytest.mark.parametrize(
    ("override", "problem"),
    [
        ({"DATABASE_URL": ""}, "DATABASE_URL"),
        ({"PROXY_SECRET": ""}, "PROXY_SECRET"),  # falls back to the dev value: rejected
        ({"PROXY_SECRET": "short"}, "PROXY_SECRET"),
        ({"IP_HASH_SALT_SEED": ""}, "IP_HASH_SALT_SEED"),
        ({"COOKIE_SECURE": "false"}, "COOKIE_SECURE"),
        ({"ENDOR_MODE": "live"}, "ENDOR_API_KEY"),
    ],
)
def test_prod_refuses_to_start_without_secrets(
    monkeypatch: pytest.MonkeyPatch, override: dict[str, str], problem: str
) -> None:
    _env(monkeypatch, {**GOOD_PROD, **override})
    with pytest.raises(ValueError, match=problem):
        Settings.from_env()


def test_game_paused_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, {"GAME_PAUSED": "true"})
    assert Settings.from_env().game_paused is True


def test_repr_hides_secrets() -> None:
    text = repr(Settings(endor_api_key="edk_x", database_url="postgresql://u:pw@h/db"))
    assert "edk_x" not in text and "pw@" not in text
