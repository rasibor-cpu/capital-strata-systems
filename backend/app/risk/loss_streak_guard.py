"""
Loss Streak Guard – REA Capital Trading Engine

Purpose:
- Block trading after N consecutive losses.
- Enforce a cooldown window after the loss streak triggers.
- Provide structured status for audit + headless runs.

Policy (per Robert):
- Trigger: 5 consecutive losses
- Cooldown: 1 hour (NOT 12 hours)
- Fail-safe: if state is invalid, default to BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


UTC = timezone.utc


@dataclass
class LossStreakPolicy:
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 60 * 60  # 1 hour


class LossStreakGuard:
    """
    Stateful loss-streak guard.

    Methods expected by engine/headless:
    - record_loss()
    - record_win()
    - should_block()
    - status()
    - reset()
    """

    def __init__(
        self,
        max_losses: int = 5,
        cooldown_hours: float = 1.0,
    ) -> None:
        # Keep names stable but map to policy
        cooldown_seconds = int(round(float(cooldown_hours) * 3600))
        self.policy = LossStreakPolicy(
            max_consecutive_losses=int(max_losses),
            cooldown_seconds=cooldown_seconds,
        )

        self._consecutive_losses: int = 0
        self._cooldown_until: Optional[datetime] = None
        self._last_event_utc: Optional[datetime] = None

    # -------------------------
    # event recorders
    # -------------------------
    def record_loss(self) -> None:
        now = datetime.now(tz=UTC)
        self._last_event_utc = now
        self._consecutive_losses += 1

        if self._consecutive_losses >= self.policy.max_consecutive_losses:
            self._cooldown_until = now + timedelta(seconds=self.policy.cooldown_seconds)

    def record_win(self) -> None:
        now = datetime.now(tz=UTC)
        self._last_event_utc = now
        # win breaks streak immediately
        self._consecutive_losses = 0
        self._cooldown_until = None

    def reset(self) -> None:
        self._consecutive_losses = 0
        self._cooldown_until = None
        self._last_event_utc = None

    # -------------------------
    # decisions
    # -------------------------
    def should_block(self) -> Dict[str, Any]:
        """
        Returns:
          {
            "decision": "ALLOW" | "BLOCK",
            "reason": str,
            "consecutive_losses": int,
            "cooldown_until_utc": str|None,
            "cooldown_remaining_seconds": int,
          }
        """
        try:
            now = datetime.now(tz=UTC)
            if self._cooldown_until and now < self._cooldown_until:
                remaining = int((self._cooldown_until - now).total_seconds())
                return {
                    "decision": "BLOCK",
                    "reason": f"Loss-streak cooldown active ({self.policy.max_consecutive_losses} losses).",
                    "consecutive_losses": self._consecutive_losses,
                    "cooldown_until_utc": self._cooldown_until.isoformat(),
                    "cooldown_remaining_seconds": max(0, remaining),
                }

            # If cooldown expired, clear it but keep streak counter (optional).
            if self._cooldown_until and now >= self._cooldown_until:
                self._cooldown_until = None

            # If we've hit threshold but cooldown cleared, allow again
            return {
                "decision": "ALLOW",
                "reason": "Loss-streak within limits.",
                "consecutive_losses": self._consecutive_losses,
                "cooldown_until_utc": None,
                "cooldown_remaining_seconds": 0,
            }
        except Exception as e:
            # fail-safe
            return {
                "decision": "BLOCK",
                "reason": f"LossStreakGuard error (fail-safe block): {type(e).__name__}: {e}",
                "consecutive_losses": self._consecutive_losses,
                "cooldown_until_utc": self._cooldown_until.isoformat() if self._cooldown_until else None,
                "cooldown_remaining_seconds": 0,
            }

    def status(self) -> Dict[str, Any]:
        block = self.should_block()
        return {
            "consecutive_losses": self._consecutive_losses,
            "max_consecutive_losses": self.policy.max_consecutive_losses,
            "cooldown_seconds": self.policy.cooldown_seconds,
            "cooldown_until_utc": self._cooldown_until.isoformat() if self._cooldown_until else None,
            "last_event_utc": self._last_event_utc.isoformat() if self._last_event_utc else None,
            "decision": block.get("decision"),
            "reason": block.get("reason"),
            "cooldown_remaining_seconds": block.get("cooldown_remaining_seconds", 0),
        }
