"""
Loss Streak Guard – REA Capital Trading Engine
---------------------------------------------

Goal:
- If consecutive losses reach threshold => BLOCK and enforce cooldown.
- Safe/structured output for audit.
- Exported API expected by headless_guarded_entry.py:

    evaluate_loss_streak(
        consecutive_losses: int,
        max_consecutive_losses: int,
        cooldown_seconds: int
    ) -> dict
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LossStreakState:
    consecutive_losses: int
    max_consecutive_losses: int
    cooldown_seconds: int
    cooldown_until_utc: str
    last_event_utc: str
    decision: str
    reason: str
    cooldown_remaining_seconds: int


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def evaluate_loss_streak(
    consecutive_losses: int,
    max_consecutive_losses: int,
    cooldown_seconds: int,
) -> Dict[str, Any]:
    """
    Decision logic:
    - If max_consecutive_losses <= 0 => BLOCK (invalid policy)
    - If consecutive_losses < max_consecutive_losses => ALLOW
    - If consecutive_losses >= max_consecutive_losses => BLOCK with cooldown
    """
    losses = max(0, _safe_int(consecutive_losses, 0))
    max_losses = _safe_int(max_consecutive_losses, 5)
    cd = _safe_int(cooldown_seconds, 3600)

    now = _now_utc()

    # invalid policy => fail closed
    if max_losses <= 0 or cd <= 0:
        state = LossStreakState(
            consecutive_losses=losses,
            max_consecutive_losses=max_losses,
            cooldown_seconds=cd,
            cooldown_until_utc="",
            last_event_utc=now.isoformat(),
            decision="BLOCK",
            reason="Invalid loss-streak policy (fail-closed).",
            cooldown_remaining_seconds=cd if cd > 0 else 0,
        )
        return state.__dict__

    # within limits
    if losses < max_losses:
        state = LossStreakState(
            consecutive_losses=losses,
            max_consecutive_losses=max_losses,
            cooldown_seconds=cd,
            cooldown_until_utc="",
            last_event_utc=now.isoformat(),
            decision="ALLOW",
            reason="Loss-streak within limits.",
            cooldown_remaining_seconds=0,
        )
        return state.__dict__

    # hit/exceeded streak => block + cooldown
    cooldown_until = now + timedelta(seconds=cd)
    state = LossStreakState(
        consecutive_losses=losses,
        max_consecutive_losses=max_losses,
        cooldown_seconds=cd,
        cooldown_until_utc=cooldown_until.isoformat(),
        last_event_utc=now.isoformat(),
        decision="BLOCK",
        reason=f"Loss-streak hit ({losses} >= {max_losses}). Cooldown active.",
        cooldown_remaining_seconds=cd,
    )
    return state.__dict__
