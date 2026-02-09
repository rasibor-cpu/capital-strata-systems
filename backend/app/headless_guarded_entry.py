"""
Headless guarded entry – REA Capital Trading Engine
DEV-safe execution harness

Fix:
- DailyTradeGuard.status() key name is not guaranteed ("trades_today" may not exist).
- We now safely infer the "trades today" counter from several possible keys
  and fall back to an internal counter if needed.
"""

from __future__ import annotations

import os
from typing import Dict, Any


def _env_bool(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _safe_trades_today(status: Dict[str, Any]) -> int:
    """
    Defensive: different implementations may expose different keys.
    We try common variants, else return 0.
    """
    if not isinstance(status, dict):
        return 0

    # Common candidates we might have used/seen across guard implementations
    candidates = [
        "trades_today",
        "trades",
        "trades_count",
        "trade_count",
        "executed_today",
        "trades_executed_today",
        "count_today",
        "today_count",
    ]
    for k in candidates:
        if k in status:
            try:
                return int(status.get(k) or 0)
            except Exception:
                return 0
    return 0


def run_headless(*, steps: int = 50, symbol: str = "EURUSD") -> Dict:
    headless_dev = _env_bool("HEADLESS_DEV_MODE", "0")
    locked = True

    from backend.app.risk.daily_trade_guard import DailyTradeGuard
    from backend.app.risk.loss_streak_guard import LossStreakGuard

    # Policy (as agreed)
    daily_guard = DailyTradeGuard(max_trades=15)
    loss_guard = LossStreakGuard(max_losses=5, cooldown_hours=1)

    steps = int(steps)

    executed = 0
    blocked_daily = 0
    blocked_loss = 0

    # Internal fallback counter in case DailyTradeGuard.status() doesn't expose one
    internal_today = 0

    for i in range(steps):
        st = daily_guard.status()
        trades_today = _safe_trades_today(st)

        # If the guard doesn't expose a usable count, use internal
        if trades_today == 0 and internal_today > 0:
            trades_today = internal_today

        # DAILY CAP CHECK
        if trades_today >= getattr(daily_guard, "max_trades", 15):
            blocked_daily += (steps - i)
            break

        # Synthetic loss every 3rd trade (keeps deterministic behaviour for testing)
        is_loss = ((i + 1) % 3 == 0)
        loss_guard.record_trade_outcome(win=not is_loss)

        dec = loss_guard.decision()
        if isinstance(dec, dict) and dec.get("decision") == "BLOCK":
            blocked_loss += (steps - i)
            break

        daily_guard.register_trade()
        internal_today += 1
        executed += 1

    return {
        "ok": True,
        "mode": "HEADLESS_DEV" if headless_dev else "HEADLESS",
        "locked": locked,
        "steps": steps,
        "symbol": symbol,
        "simulated_trades": executed,
        "blocked_trades": blocked_daily + blocked_loss,
        "blocked_breakdown": {
            "daily_cap": blocked_daily,
            "loss_streak_cooldown": blocked_loss,
        },
        "daily_trade_guard": daily_guard.status(),
        "loss_streak_guard": loss_guard.public_status(),
        "live_execution": False,
    }
