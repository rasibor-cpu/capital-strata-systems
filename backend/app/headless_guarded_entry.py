"""
Headless Guarded Entry – REA Capital Trading Engine
---------------------------------------------------
Dev-safe headless execution wrapper that applies:
- DailyTradeGuard
- LossStreakGuard
Returns structured response ALWAYS (never empty result).
"""

from __future__ import annotations

from typing import Dict, Any

from backend.app.risk.daily_trade_guard import DailyTradeGuard
from backend.app.risk.loss_streak_guard import LossStreakGuard


# Engine-lifetime guards (simple in-memory singletons for HEADLESS_DEV)
daily_guard = DailyTradeGuard(max_trades=10)
loss_guard = LossStreakGuard(max_losses=5, cooldown_hours=1)  # ✅ 1 hour cooldown after 5 losses


def run_headless(steps: int, symbol: str) -> Dict[str, Any]:
    # ---------------------------
    # 1) Daily Guard
    # ---------------------------
    daily_status = daily_guard.status()
    if not daily_status.get("allowed", False):
        return {
            "ok": True,
            "mode": "HEADLESS_DEV",
            "locked": True,
            "symbol": symbol,
            "steps_requested": steps,
            "reason": "DAILY_TRADE_LIMIT_REACHED",
            "daily_trade_guard": daily_status,
            "loss_streak_guard": loss_guard.status(),
            "live_execution": False,
        }

    # ---------------------------
    # 2) Loss Streak Guard
    # ---------------------------
    loss_status = loss_guard.status()
    if not loss_status.get("allowed", False):
        return {
            "ok": True,
            "mode": "HEADLESS_DEV",
            "locked": True,
            "symbol": symbol,
            "steps_requested": steps,
            "reason": "LOSS_STREAK_COOLDOWN_ACTIVE",
            "daily_trade_guard": daily_status,
            "loss_streak_guard": loss_status,
            "live_execution": False,
        }

    # ---------------------------
    # 3) Simulated “trade attempts”
    # ---------------------------
    remaining = int(daily_status.get("remaining", 0))
    simulated_trades = min(int(steps), max(0, remaining))
    blocked_trades = max(0, int(steps) - simulated_trades)

    for _ in range(simulated_trades):
        daily_guard.record_trade()

    # IMPORTANT:
    # In HEADLESS_DEV we are NOT generating real PnL yet.
    # So we do NOT call loss_guard.record_trade_outcome(...) here.
    # When we wire real paper execution, outcomes will feed this.

    return {
        "ok": True,
        "mode": "HEADLESS_DEV",
        "locked": True,  # ✅ keep execution layer locked in dev until live adapter gate is ready
        "symbol": symbol,
        "steps_requested": steps,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "daily_trade_guard": daily_guard.status(),
        "loss_streak_guard": loss_guard.status(),
        "live_execution": False,
    }
