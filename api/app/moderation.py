"""Input moderation: reject text that looks like a real secret (docs/PRD.md 4.2),
and validate player handles.

Deliberately narrow. Long base64 strings are NOT rejected on their own: base64
obfuscation is a core attack the game exists to collect (family F7). Only
obvious real-secret formats are blocked: private key blocks, well-known token
prefixes, JWTs, personal emails and Luhn-valid card numbers. SSH public keys are
allowed (goal 10 attacks use them, and they are not secrets). Shell `user@host`
targets (`scp .env deploy@host:`, `git@github.com:org/repo`) are not emails.
"""

import re
from typing import Final

SECRET_MESSAGE: Final = (
    "This looks like a real secret (a private key, access token, email or card number). "  # noqa: S105
    "Remove it. Do not paste real secrets."
)

_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
_TOKENS = re.compile(
    r"\bAKIA[0-9A-Z]{16}\b"  # AWS access key id
    r"|\bgh[pousr]_[A-Za-z0-9]{36,}\b"  # GitHub tokens
    r"|\bgithub_pat_[A-Za-z0-9_]{50,}\b"
    r"|\bsk-(?:ant-|proj-|live_|test_)?[A-Za-z0-9_-]{20,}\b"  # OpenAI / Anthropic / Stripe style
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}\b"  # Slack
    r"|\bedk_[A-Za-z0-9_-]{16,}\b"  # decision platform API keys
    r"|\bAIza[0-9A-Za-z_-]{35}\b"  # Google API key
    r"|\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"  # JWT
)
_EMAIL = re.compile(
    r"\b(?P<local>[A-Za-z0-9._%+-]+)@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b(?P<colon>:)?"
)
# Login names that appear in ssh/scp/git targets, never a person's email.
_SYSTEM_USERS: Final = frozenset(
    {
        "git",
        "root",
        "user",
        "ubuntu",
        "admin",
        "deploy",
        "ec2-user",
        "debian",
        "centos",
        "pi",
        "www-data",
        "postgres",
        "ops",
        "dev",
        "ci",
        "runner",
        "app",
    }
)
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){14,15}\d\b")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def looks_like_secret(text: str) -> bool:
    if _PRIVATE_KEY.search(text) or _TOKENS.search(text):
        return True
    for match in _EMAIL.finditer(text):
        if match.group("colon") or match.group("local").lower() in _SYSTEM_USERS:
            continue  # a shell target, not a personal email
        return True
    for match in _CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) in (15, 16) and _luhn_ok(digits):
            return True
    return False


# --- handles ----------------------------------------------------------------

_HANDLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{1,18}[A-Za-z0-9_]$")
# Kept short and generic; matched against the handle with separators removed.
_BLOCKED: Final = (
    "fuck",
    "shit",
    "cunt",
    "nigg",
    "fag",
    "rape",
    "nazi",
    "hitler",
    "admin",
    "moderator",
)


def handle_problem(handle: str) -> str | None:
    """None if the handle is fine, else a message for the player."""
    if not 3 <= len(handle) <= 20:
        return "Handle must be 3 to 20 characters."
    if not _HANDLE.match(handle):
        return "Use letters, numbers, spaces, dots, dashes or underscores."
    squashed = re.sub(r"[^a-z0-9]", "", handle.lower())
    if any(word in squashed for word in _BLOCKED):
        return "Pick a different handle."
    return None
