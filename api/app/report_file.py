"""Read the published evaluation summary without inventing report numbers."""

import json
from pathlib import Path
from typing import Any, cast

REPORT_PATH = Path(__file__).resolve().parents[1] / "config" / "report.json"


def published_report(path: Path = REPORT_PATH) -> dict[str, Any] | None:
    """Return a report produced by ml/scripts/report.py, or no report."""
    if not path.is_file():
        return None
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    report = cast(dict[str, Any], raw)
    if not isinstance(report.get("gate_version"), str):
        return None
    if not isinstance(report.get("models"), list) or not isinstance(report.get("limits"), list):
        return None
    return report
