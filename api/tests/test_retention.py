"""Retention job matches the promise on /privacy (PRD 4.2)."""

import asyncio
import os

import pytest

from app.store import retention


def test_retention_windows_match_the_privacy_page() -> None:
    assert retention.RAW_RETENTION == "90 days"
    assert retention.IDEMPOTENCY_RETENTION == "10 minutes"
    tables = [t for t, _, _ in retention.PURGES]
    assert tables == ["attempts", "sessions", "idempotency_keys"]
    assert "evals" not in tables  # aggregates are kept
    for table, count_sql, delete_sql in retention.PURGES:
        window = (
            retention.IDEMPOTENCY_RETENTION
            if table == "idempotency_keys"
            else retention.RAW_RETENTION
        )
        assert f"interval '{window}'" in count_sql
        assert f"interval '{window}'" in delete_sql
        assert f" {table} " in count_sql
        assert delete_sql.split("delete from ")[1].startswith(table + " ")


def test_retention_needs_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert asyncio.run(retention._main(dry_run=True)) == 2  # pyright: ignore[reportPrivateUsage]


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL")
def test_retention_dry_run_changes_nothing() -> None:
    from psycopg import AsyncConnection

    async def go() -> dict[str, int]:
        url = os.environ["TEST_DATABASE_URL"]
        async with await AsyncConnection.connect(url, prepare_threshold=None) as conn:
            return await retention.purge(conn, dry_run=True)

    assert set(asyncio.run(go())) == {"attempts", "sessions", "idempotency_keys"}
