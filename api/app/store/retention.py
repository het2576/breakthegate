"""Retention job (PRD 4.2): raw attempts 90 days, idempotency keys 10 minutes.

    uv run python -m app.store.retention            # uses DATABASE_URL
    uv run python -m app.store.retention --dry-run  # count what would go, change nothing

Run daily from the Render cron. Reveals cascade with their attempt. Sessions older
than the cookie lifetime go too, which drops their hashed IP and handle. Eval files
are aggregates and are kept.
"""

import argparse
import asyncio
import os
import sys
from typing import LiteralString

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

RAW_RETENTION = "90 days"
IDEMPOTENCY_RETENTION = "10 minutes"

# (table, count query, delete query). Literal SQL only: nothing here comes from input.
PURGES: tuple[tuple[str, LiteralString, LiteralString], ...] = (
    (
        "attempts",
        "select count(*) from attempts where created_at < now() - interval '90 days'",
        "with gone as (delete from attempts where created_at < now() - interval '90 days'"
        " returning 1) select count(*) from gone",
    ),
    (
        "sessions",
        "select count(*) from sessions where created_at < now() - interval '90 days'",
        "with gone as (delete from sessions where created_at < now() - interval '90 days'"
        " returning 1) select count(*) from gone",
    ),
    (
        "idempotency_keys",
        "select count(*) from idempotency_keys where created_at < now() - interval '10 minutes'",
        "with gone as (delete from idempotency_keys"
        " where created_at < now() - interval '10 minutes' returning 1)"
        " select count(*) from gone",
    ),
)


async def purge(conn: AsyncConnection[TupleRow], *, dry_run: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with conn.transaction():
        for table, count_sql, delete_sql in PURGES:
            cur = await conn.execute(count_sql if dry_run else delete_sql)
            row = await cur.fetchone()
            counts[table] = int(row[0]) if row else 0
    return counts


async def _main(dry_run: bool) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    async with await AsyncConnection.connect(url, prepare_threshold=None) as conn:
        counts = await purge(conn, dry_run=dry_run)
    label = "would delete" if dry_run else "deleted"
    print(label + ": " + ", ".join(f"{t}={n}" for t, n in counts.items()))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(_main(parser.parse_args().dry_run)))
