"""Build deterministic Endor-ready splits from reviewed JSONL seed rows.

Input rows are review artifacts, never uploaded directly. Each must contain
``id``, ``base_id``, ``task``, ``command``, and ``safe``. Optional ``family``
and ``weight`` stay in metadata only. Variants must retain their source
``base_id`` so no command family can leak between splits.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import yaml

Split = Literal["train", "validation", "test"]


def stable_split(base_id: str, seed: str = "btg-v1") -> Split:
    """Use a stable hash to assign a whole base to 60/20/20 splits."""
    bucket = int(hashlib.sha256(f"{seed}:{base_id}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 60 else "validation" if bucket < 80 else "test"


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number} is not JSON") from exc
            required = {"id", "base_id", "task", "command", "safe"}
            if not required <= row.keys() or not isinstance(row["safe"], bool):
                raise ValueError(f"{path}:{number} must have {sorted(required)} and boolean safe")
            rows.append(row)
    ids = [str(row["id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("seed row ids must be unique")
    return rows


def question_text(gates: Path, variant: str) -> str:
    questions = yaml.safe_load(gates.read_text(encoding="utf-8"))["questions"]
    key = "safe_q0" if variant == "q0" else "safe_q1"
    value = questions.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{gates} has no {key} question")
    return value


def endor_row(row: dict[str, Any], question: str) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "state": {"task": row["task"], "command": row["command"]},
        "questions": {"safe": {"type": "noul", "instructions": question}},
        "labels": {"safe": row["safe"]},
        "weight": float(row.get("weight", 1.0)),
    }


def build(rows: list[dict[str, Any]], question: str, output_dir: Path, *, seed: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assignments = {str(row["base_id"]): stable_split(str(row["base_id"]), seed) for row in rows}
    groups: dict[Split, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    metadata: list[dict[str, Any]] = []
    for row in rows:
        split = assignments[str(row["base_id"])]
        groups[split].append(endor_row(row, question))
        metadata.append({
            "id": str(row["id"]), "base_id": str(row["base_id"]), "split": split,
            "family": str(row.get("family", "clean")), "safe": row["safe"],
        })
    for split, group in groups.items():
        (output_dir / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in group), encoding="utf-8"
        )
    (output_dir / "meta.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in metadata), encoding="utf-8"
    )
    hashes = {
        split: hashlib.sha256((output_dir / f"{split}.jsonl").read_bytes()).hexdigest()
        for split in groups
    }
    manifest = {
        "seed": seed,
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
        "rows": {split: len(group) for split, group in groups.items()},
        "bases": {split: len({row["base_id"] for row in metadata if row["split"] == split}) for split in groups},
        "sha256": hashes,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True, help="Reviewed seed JSONL; repeatable")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gates", type=Path, default=Path(__file__).resolve().parents[2] / "api/config/gates.yaml")
    parser.add_argument("--question", choices=("q0", "q1"), default="q1")
    parser.add_argument("--seed", default="btg-v1")
    args = parser.parse_args()
    manifest = build(load_rows(args.input), question_text(args.gates, args.question), args.output_dir, seed=args.seed)
    print("built " + ", ".join(f"{name}={count}" for name, count in manifest["rows"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
