"""Validate an evaluation artifact and publish its exact summary for the API."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def prepare_report(eval_path: Path) -> dict[str, Any]:
    """Return report data with provenance, rejecting incomplete evaluation files."""
    source = eval_path.read_bytes()
    try:
        report = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError("evaluation file is not valid JSON") from exc
    if not isinstance(report.get("gate_version"), str) or not isinstance(report.get("models"), list):
        raise ValueError("evaluation needs gate_version and models")
    if not isinstance(report.get("limits"), list):
        raise ValueError("evaluation needs a limits list")
    for model in report["models"]:
        if not isinstance(model, dict) or not all(key in model for key in ("name", "tau", "asr", "fbr", "n")):
            raise ValueError("every model needs name, tau, asr, fbr and n")
    report["date"] = report.get("date") or datetime.now(UTC).date().isoformat()
    report["file_hash"] = hashlib.sha256(source).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "api/config/report.json")
    args = parser.parse_args()
    report = prepare_report(args.eval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"published {args.output} for {report['gate_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
