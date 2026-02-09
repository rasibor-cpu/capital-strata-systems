"""
Headless Guarded Entry
----------------------
Central orchestration layer for:

- Daily trade guard
- Loss streak guard (1h cooldown after 5 losses)
- Position concurrency guard (max 20 open positions)
- Execution layer lock (live disabled by default)
"""

from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.risk.daily_trade_guard import DailyTradeGuard
from backend.app.risk.loss_streak_guard import LossStreakGuard
from backend.app.risk.position_guard import (
    PositionGuard,
    PositionPolicy,
    PositionState,
)


def run_headless(steps: int, symbol: str, execution_mode: str = "SIMULATION") -> Dict[str, Any]:

    timestamp_utc = datetime.now(timezone.utc).isoformat()

    # -------------------------
    # DAILY TRADE GUARD
    # -------------------------
    daily_guard = DailyTradeGuard(max_trades=15)
    daily_result = daily_guard.evaluate()

    # -------------------------
    # LOSS STREAK GUARD
    # -------------------------
    loss_guard = LossStreakGuard(
        max_consecutive_losses=5,
        cooldown_seconds=3600,  # 1 hour
    )

    loss_result = loss_guard.evaluate()

    # -------------------------
    # POSITION CONCURRENCY GUARD
    # -------------------------
    position_policy = PositionPolicy(max_concurrent_positions=20)
    position_guard = PositionGuard(position_policy)

    # For now simulate zero open positions
    current_open_positions = 0

    position_result = position_guard.evaluate(
        PositionState(open_positions=current_open_positions)
    )

    # -------------------------
    # BLOCK LOGIC
    # -------------------------
    blocked_reason = None

    if not daily_result["allowed"]:
        blocked_reason = "Daily trade limit reached"

    elif loss_result["decision"] == "BLOCK":
        blocked_reason = loss_result["reason"]

    elif position_result["decision"] == "BLOCK":
        blocked_reason = position_result["reason"]

    # -------------------------
    # EXECUTION LAYER (LOCKED)
    # -------------------------
    live_execution = False

    trade_preview = {
        "symbol": symbol,
        "side": "buy",
        "units": 1,
        "order_type": "MARKET",
    }

    # -------------------------
    # RESULT
    # -------------------------
    return {
        "ok": True,
        "mode": execution_mode,
        "live_execution": live_execution,
        "steps_requested": steps,
        "symbol": symbol,
        "daily_trade_guard": daily_result,
        "loss_streak_guard": loss_result,
        "position_guard": position_result,
        "trade_preview": trade_preview,
        "blocked_reason": blocked_reason or "Execution layer locked (no live trades).",
        "timestamp_utc": timestamp_utc,
    }
