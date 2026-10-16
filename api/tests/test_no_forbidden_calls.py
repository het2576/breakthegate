"""Safety: no command execution primitives anywhere under app/ (docs/PRD.md 4.1).

Commands are opaque strings everywhere. This greps the source for the builtins
that could run them. The patterns match actual calls, not lookalikes such as
`evaluate_attempt` (which contains the substring "eval").
"""

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

FORBIDDEN = [
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bos\.system\b"),
    re.compile(r"(?<![A-Za-z_.])eval\s*\("),
    re.compile(r"(?<![A-Za-z_.])exec\s*\("),
    re.compile(r"\bos\.popen\b"),
]


def test_no_forbidden_calls_in_app() -> None:
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{line} -> {pattern.pattern}")
    assert not offenders, "forbidden execution primitives found:\n" + "\n".join(offenders)
