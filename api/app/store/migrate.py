"""Apply SQL migrations in order, once each (infra/supabase/migrations/*.sql).

    uv run python -m app.store.migrate            # uses DATABASE_URL
    uv run python -m app.store.migrate --dry-run  # list pending, change nothing

Applied versions are recorded in schema_migrations. Each file runs in its own
transaction. File names follow the Supabase CLI convention (<timestamp>_name.sql)
so the CLI can apply the same files.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "infra" / "supabase" / "migrations"


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"))


async def pending(
    conn: AsyncConnection[TupleRow], directory: Path = MIGRATIONS_DIR, *, initialize: bool = True
) -> list[Path]:
    """Return unapplied migrations, optionally without creating bookkeeping state."""
    if not initialize:
        cursor = await conn.execute("select to_regclass('public.schema_migrations')")
        table = await cursor.fetchone()
        if table is None or table[0] is None:
            return migration_files(directory)
    else:
        await conn.execute(
            "create table if not exists schema_migrations "
            "(version text primary key, applied_at timestamptz not null default now())"
        )
    cur = await conn.execute("select version from schema_migrations")
    applied = {str(row[0]) for row in await cur.fetchall()}
    await conn.commit()
    return [f for f in migration_files(directory) if f.stem not in applied]


async def apply_migrations(
    conn: AsyncConnection[TupleRow], directory: Path = MIGRATIONS_DIR
) -> list[str]:
    """Apply every pending migration; return the versions applied."""
    done: list[str] = []
    for path in await pending(conn, directory):
        async with conn.transaction():
            # bytes: a whole file of trusted SQL, sent as one multi-statement query
            await conn.execute(path.read_bytes())
            await conn.execute("insert into schema_migrations (version) values (%s)", (path.stem,))
        done.append(path.stem)
    return done


async def _main(dry_run: bool) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    async with await AsyncConnection.connect(url, prepare_threshold=None) as conn:
        todo = await pending(conn, initialize=not dry_run)
        if dry_run:
            print("pending:", ", ".join(p.stem for p in todo) or "none")
            return 0
        applied = await apply_migrations(conn)
        print("applied:", ", ".join(applied) or "none")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(_main(parser.parse_args().dry_run)))
