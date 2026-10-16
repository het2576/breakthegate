"""Export consented, verified game attempts for offline training.

Run with the API environment because it supplies psycopg and PyYAML:

    cd api && uv run python ../ml/scripts/export_attempts.py --output-dir ../ml/data/raw/game-export

The exporter only reads Postgres. It never calls the decision platform, and it
does not execute or interpret command strings. Splits are assigned by session
before time buckets, so one player cannot appear in two splits.
"""

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[2]
GATES_PATH = ROOT.parent / "api" / "config" / "gates.yaml"
Split = Literal["train", "validation", "test"]


@dataclass(frozen=True)
class Attempt:
    id: str
    session_id: str
    task: str
    command: str
    created_at: datetime


def split_sessions(attempts: list[Attempt]) -> dict[str, Split]:
    """Assign whole sessions in chronological order: 70% / 15% / 15%."""
    first_seen: dict[str, datetime] = {}
    for attempt in attempts:
        first_seen[attempt.session_id] = min(first_seen.get(attempt.session_id, attempt.created_at), attempt.created_at)
    sessions = sorted(first_seen, key=lambda session_id: (first_seen[session_id], session_id))
    n = len(sessions)
    train_end = (n * 70 + 99) // 100
    validation_end = (n * 85 + 99) // 100
    result: dict[str, Split] = {}
    for index, session_id in enumerate(sessions):
        result[session_id] = "train" if index < train_end else "validation" if index < validation_end else "test"
    return result


def load_question(path: Path) -> str:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    question = raw["questions"]["safe_q1"]
    if not isinstance(question, str) or not question:
        raise ValueError("gates.yaml has no safe_q1 text")
    return question


def endor_row(attempt: Attempt, question: str) -> dict[str, Any]:
    return {
        "id": f"game-{attempt.id}",
        "state": {"task": attempt.task, "command": attempt.command},
        "questions": {"safe": {"type": "noul", "instructions": question}},
        "labels": {"safe": False},
        "weight": 1.0,
    }


def read_attempts(database_url: str) -> list[Attempt]:
    # `a.consent_training` captures consent at the moment of submission. The
    # join makes deleted sessions an explicit exclusion even before cascade cleanup.
    query = """
        select a.id::text, a.session_id::text, a.task, a.command, a.created_at
        from attempts a
        join sessions s on s.id = a.session_id
        where a.consent_training
          and a.verified is true
          and a.verify_p is not null
          and s.deleted_at is null
        order by a.created_at asc, a.id asc
    """
    with psycopg.connect(database_url) as conn, conn.cursor() as cursor:
        cursor.execute(query)
        return [Attempt(*row) for row in cursor.fetchall()]


def write_export(attempts: list[Attempt], question: str, output_dir: Path) -> dict[Split, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[Split, list[Attempt]] = defaultdict(list)
    assignments = split_sessions(attempts)
    for attempt in attempts:
        groups[assignments[attempt.session_id]].append(attempt)

    counts: dict[Split, int] = {}
    for split in ("train", "validation", "test"):
        path = output_dir / f"{split}.jsonl"
        rows = groups[split]
        with path.open("w", encoding="utf-8") as file:
            for attempt in rows:
                file.write(json.dumps(endor_row(attempt, question), separators=(",", ":")) + "\n")
        counts[split] = len(rows)

    manifest = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "rows": counts,
        "sessions": {split: len({attempt.session_id for attempt in groups[split]}) for split in counts},
        "policy": "consented, verified attempts only; session-disjoint chronological splits",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Export consented Break the Gate attempts.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gates", type=Path, default=GATES_PATH)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("DATABASE_URL or --database-url is required")
    attempts = read_attempts(args.database_url)
    counts = write_export(attempts, load_question(args.gates), args.output_dir)
    print("exported " + ", ".join(f"{split}={count}" for split, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
