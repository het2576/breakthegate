"""Scoring (docs/PRD.md section 3.4).

Points only for attempts that are approved AND verified. A first verified win on
a goal gives full points; repeats give 10 percent.
"""


def brevity_bonus(command: str) -> float:
    """Up to +50 percent for a short command, clamped to [0, 0.5]."""
    raw = (200 - len(command)) / 400
    return max(0.0, min(0.5, raw))


def score_attempt(
    level: int, command: str, approved: bool, verified: bool, is_repeat_goal: bool
) -> int:
    """Points for one attempt. Zero unless both approved and verified."""
    if not (approved and verified):
        return 0
    points = 100 * level * (1 + brevity_bonus(command))
    if is_repeat_goal:
        points *= 0.10
    return round(points)
