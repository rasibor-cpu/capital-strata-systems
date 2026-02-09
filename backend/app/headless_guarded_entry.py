"""
Headless guarded entry – REA Capital Trading Engine
Self-contained version (no simulator dependency)
"""

from __future__ import annotations

import os
from typing import Dict


def _env_bool(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).lower() in ("1", "true", "yes", "y", "on")


def run_headless(*, steps: int = 50, symbol: str = "EURUSD", **_ignored) -> Dict:
    headless_dev = _env_bool("HEADLESS_DEV_MODE", "0")
    locked = True

    # --- Daily Trade Guard ---
    from backend.app.risk.daily_trade_guard import DailyTradeGuard

    guard = DailyTradeGuard(max_trades=15)

    steps = int(steps)

    # Simulate trades internally
    simulated_trades = steps
    allowed_trades = min(simulated_trades, guard.max_trades)
    blocked_trades = max(0, simulated_trades - guard.max_trades)

    for _ in range(allowed_trades):
        guard.register_trade()

    return {
        "mode": "HEADLESS_DEV" if headless_dev else "HEADLESS",
        "symbol": symbol,
        "steps_requested": steps,
        "simulated_trades": allowed_trades,
        "blocked_trades": blocked_trades,
        "live_execution": False,
        "locked": locked,
        "daily_trade_guard": guard.status(),
    }
