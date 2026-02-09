"""
Loss Streak Guard – REA Capital Trading Engine
----------------------------------------------

Purpose:
- Block trading after N consecutive losses for a cooldown period.
- Safe defaults: if unsure, block.
- Cooldown is configured in hours (cooldown_hours).

Policy:
- max_losses = 5
- cooldown_hours = 1   (per Robert requirement)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any


@dataclass
class LossStreakPolicy:
    max_losses: int = 5
    cooldown_hours: float = 1.0


class LossStreakGuard:
    def __init__(self, max_losses: int = 5, cooldown_hours: float = 1.0):
        if max_losses <= 0:
            raise ValueError("max_losses must be >= 1")
        if cooldown_hours <= 0:
            raise ValueError("cooldown_hours must be > 0")

        self.policy = LossStreakPolicy(max_losses=max_losses, cooldown_hours=cooldown_hours)

        self._consecutive_losses: int = 0
        self._cooldown_until: Optional[datetime] = None

    # ---------------------------
    # Core helpers
    # ---------------------------

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _in_cooldown(self) -> bool:
        if self._cooldown_until is None:
            return False
        return self._now() < self._cooldown_until

    # ---------------------------
    # Public API
    # ---------------------------

    def record_trade_outcome(self, win: bool) -> None:
        """
        Update loss streak state based on trade outcome.
        - win=True  -> reset consecutive losses and clear cooldown if any
        - win=False -> increment losses; if hits max_losses -> trigger cooldown
        """
        if win:
            self._consecutive_losses = 0
            self._cooldown_until = None
            return

        # loss
        self._consecutive_losses += 1

        if self._consecutive_losses >= self.policy.max_losses:
            self._cooldown_until = self._now() + timedelta(hours=self.policy.cooldown_hours)

    def reset(self) -> None:
        self._consecutive_losses = 0
        self._cooldown_until = None

    def status(self) -> Dict[str, Any]:
        in_cd = self._in_cooldown()
        now = self._now()

        return {
            "allowed": (not in_cd),
            "consecutive_losses": self._consecutive_losses,
            "max_losses": self.policy.max_losses,
            "cooldown_hours": self.policy.cooldown_hours,
            "in_cooldown": in_cd,
            "cooldown_until_utc": (self._cooldown_until.isoformat() if self._cooldown_until else None),
            "now_utc": now.isoformat(),
            "reason": ("COOLDOWN_ACTIVE" if in_cd else "OK"),
        }
