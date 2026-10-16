"""Pure tests for the offline consented-attempt export split policy."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _export_module() -> Any:
    path = Path(__file__).resolve().parents[2] / "ml" / "scripts" / "export_attempts.py"
    spec = importlib.util.spec_from_file_location("export_attempts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_split_is_session_disjoint_and_chronological() -> None:
    module = _export_module()
    Attempt = module.Attempt
    start = datetime(2026, 10, 16, tzinfo=UTC)
    attempts = [
        Attempt("a", "one", "task", "command", start),
        Attempt("b", "one", "task", "command", start + timedelta(days=3)),
        Attempt("c", "two", "task", "command", start + timedelta(days=1)),
        Attempt("d", "three", "task", "command", start + timedelta(days=2)),
        Attempt("e", "four", "task", "command", start + timedelta(days=4)),
        Attempt("f", "five", "task", "command", start + timedelta(days=5)),
        Attempt("g", "six", "task", "command", start + timedelta(days=6)),
        Attempt("h", "seven", "task", "command", start + timedelta(days=7)),
    ]
    splits = module.split_sessions(attempts)
    assert splits["one"] == "train" and splits["seven"] == "test"
    assert len(set(splits)) == 7
