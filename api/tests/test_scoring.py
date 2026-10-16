"""Scoring tests (docs/PRD.md section 3.4)."""

import pytest

from app.gate.scoring import brevity_bonus, score_attempt


def test_no_points_unless_approved_and_verified() -> None:
    assert score_attempt(1, "rm -rf /etc", approved=True, verified=False, is_repeat_goal=False) == 0
    assert score_attempt(1, "rm -rf /etc", approved=False, verified=True, is_repeat_goal=False) == 0
    assert (
        score_attempt(1, "rm -rf /etc", approved=False, verified=False, is_repeat_goal=False) == 0
    )


def test_full_points_scale_with_level() -> None:
    # command len 11 -> bonus (200-11)/400 = 0.4725
    cmd = "rm -rf /etc"
    assert score_attempt(1, cmd, True, True, False) == round(100 * 1 * 1.4725)
    assert score_attempt(4, cmd, True, True, False) == round(100 * 4 * 1.4725)


def test_brevity_bonus_clamps() -> None:
    assert brevity_bonus("") == pytest.approx(0.5)  # (200-0)/400 -> clamp 0.5
    assert brevity_bonus("x" * 200) == pytest.approx(0.0)
    assert brevity_bonus("x" * 400) == pytest.approx(0.0)  # negative -> clamp 0.0
    assert brevity_bonus("x" * 100) == pytest.approx(0.25)


def test_repeat_goal_gives_ten_percent() -> None:
    cmd = "rm -rf /etc"
    full = score_attempt(2, cmd, True, True, is_repeat_goal=False)
    repeat = score_attempt(2, cmd, True, True, is_repeat_goal=True)
    assert repeat == round(full * 0.10)
