"""
Daily Trade Guard – REA Capital Trading Engine
---------------------------------------------
Purpose:
- Enforce max number of trades per day (UTC day).
- Safe output: always returns structured dict.

This module exports:
- evaluate_daily_trade_guard(trades_today: int, max_trades: int) -> dict
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def evaluate_daily_trade_guard(trades_today: int, max_trades: int) -> Dict[str, object]:
    # sanitize
    try:
        trades_today_i = int(trades_today)
    except Exception:
        trades_today_i = 0

    try:
        max_trades_i = int(max_trades)
    except Exception:
        max_trades_i = 0

    if max_trades_i < 0:
        max_trades_i = 0
    if trades_today_i < 0:
        trades_today_i = 0

    remaining = max(0, max_trades_i - trades_today_i)
    allowed = trades_today_i < max_trades_i if max_trades_i > 0 else False

    current_day = datetime.now(timezone.utc).date().isoformat()

    return {
        "current_day": current_day,
        "trades_today": trades_today_i,
        "max_trades": max_trades_i,
        "remaining": remaining,
        "allowed": allowed,
    }
