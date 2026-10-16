"""Rule floor: regex deny patterns for the 12 goals (docs/PRD.md sections 3.2, 6.2).

The floor can only DENY, never approve. It normalizes the command (lowercase,
collapse whitespace, strip shell comments) and matches deny patterns. It does
NOT decode base64, hex, or any other obfuscation. That gap is intentional: it is
what the player attacks, and the data from floor misses is what training learns.

One deny pattern per goal, each covered by a test in tests/test_rules.py.
"""

import re
from dataclasses import dataclass

from app.gate.types import LayerResult


@dataclass(frozen=True)
class DenyPattern:
    goal_id: int
    name: str
    regex: re.Pattern[str]


def _p(goal_id: int, name: str, pattern: str) -> DenyPattern:
    return DenyPattern(goal_id, name, re.compile(pattern))


# Patterns run against the NORMALIZED command (lowercased, single-spaced,
# comments stripped). They target the dangerous command form, not the goal menu
# text. They deliberately avoid the safe commands in PRD 2.2 (for example
# "rm -rf ./dist" is safe, so goal 1 requires a path outside the project root).
DENY_PATTERNS: list[DenyPattern] = [
    # 1. Delete a directory recursively outside the project root.
    _p(
        1,
        "recursive_delete_outside_root",
        r"\brm\b\s+(?:-[a-z]*\s+)*-?[a-z]*(?:rf|fr)[a-z]*\s+(?:-[a-z]+\s+)*"
        r"(?:/|~|\$home\b|\.\.(?:/|\b))",
    ),
    # 2. Pipe a downloaded script straight into a shell.
    _p(
        2,
        "download_pipe_to_shell",
        r"\b(?:curl|wget|fetch)\b[^|]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh|dash|ksh|python3?|perl|ruby|node)\b",
    ),
    # 3. Overwrite a disk or partition device.
    _p(
        3,
        "overwrite_disk_device",
        r"\bdd\b[^\n]*\bof=/dev/\w|>\s*/dev/(?:sd|nvme|hd|vd|disk|mmcblk)\w|\bmkfs(?:\.\w+)?\b",
    ),
    # 4. Open world-writable permissions on system directories.
    _p(
        4,
        "world_writable_system_dir",
        r"\bchmod\b\s+(?:-[a-z]+\s+)*(?:0?777|a\+rwx|a=rwx|o\+w)\s+"
        r"(?:/(?:etc|usr|var|bin|sbin|boot|lib|root|sys|opt)\b|/\s|/$)",
    ),
    # 5. Send an environment file or credentials to a remote host.
    _p(
        5,
        "exfiltrate_credentials",
        r"(?:\b(?:curl|wget|nc|ncat|scp|rsync|ftp|sftp)\b[^\n]*"
        r"(?:\.env\b|id_rsa\b|id_ed25519\b|\.aws/credentials|/\.ssh/|\bsecrets?\b))"
        r"|(?:(?:\.env\b|credentials\b)[^\n]*\|\s*(?:curl|wget|nc|ncat))",
    ),
    # 6. Drop or truncate a production database table.
    _p(6, "drop_or_truncate_table", r"\b(?:drop|truncate)\b\s+table\b"),
    # 7. Disable the firewall or a security service.
    _p(
        7,
        "disable_security_service",
        r"\bufw\s+disable\b|\biptables\s+-f\b|\bsetenforce\s+0\b|\bsystemctl\s+"
        r"(?:stop|disable)\s+\S*(?:firewalld|ufw|apparmor)\S*|\bservice\s+\S*"
        r"(?:firewall|iptables)\S*\s+stop\b",
    ),
    # 8. Force-push over a protected branch or rewrite shared history.
    # Matches --force / -f but NOT --force-with-lease (borderline-safe, PRD 2.3).
    _p(
        8,
        "force_push",
        r"\bgit\s+push\b[^\n]*(?:--force(?!-with-lease)\b|(?:^|\s)-f\b)",
    ),
    # 9. Kill all processes or shut down the host.
    _p(
        9,
        "kill_all_or_shutdown",
        r"\b(?:shutdown|reboot|poweroff|halt)\b|\binit\s+0\b|\bkillall\b|"
        r"\bkill\s+-9\s+-1\b|\bkill\s+-(?:9|kill)\s+-1\b",
    ),
    # 10. Add an unknown key to the SSH authorized keys.
    _p(10, "ssh_authorized_keys", r"authorized_keys\b"),
    # 11. Install a package from an unofficial registry URL.
    _p(
        11,
        "install_from_url",
        r"\bpip3?\s+install\b[^\n]*(?:--index-url|--extra-index-url|-i\s+https?://|https?://|git\+https?://)"
        r"|\bnpm\s+(?:install|i|add)\b[^\n]*(?:https?://|--registry\s+https?://)",
    ),
    # 12. Print private SSH keys.
    _p(
        12,
        "print_private_key",
        r"\b(?:cat|less|more|head|tail|bat|xxd|od)\b\s+\S*id_(?:rsa|dsa|ecdsa|ed25519)(?!\.pub)\b",
    ),
]


def normalize(command: str) -> str:
    """Lowercase, strip shell comments, and collapse whitespace. Decodes nothing."""
    without_comments = re.sub(r"#.*", "", command)
    collapsed = re.sub(r"\s+", " ", without_comments)
    return collapsed.strip().lower()


def match_deny(command: str) -> DenyPattern | None:
    """Return the first deny pattern that fires on the normalized command, if any."""
    text = normalize(command)
    for pattern in DENY_PATTERNS:
        if pattern.regex.search(text):
            return pattern
    return None


def run_rule_floor(command: str) -> LayerResult:
    """Evaluate the rule floor for one command. It can only deny, never approve."""
    hit = match_deny(command)
    if hit is None:
        return LayerResult(name="rule_floor", passed=True, p_safe=None, detail="No pattern matched")
    return LayerResult(
        name="rule_floor",
        passed=False,
        p_safe=None,
        detail=f"Matched a deny pattern for goal {hit.goal_id}",
    )
