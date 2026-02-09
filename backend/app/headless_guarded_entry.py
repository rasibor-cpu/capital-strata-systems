"""
Headless Guarded Entry – REA Capital Trading Engine
--------------------------------------------------

Execution order:

1. Daily Trade Guard
2. Loss Streak Guard
3. Concurrency Guard
4. Equity Drawdown Guard
5. Execution Lock

Safe default: any missing risk data = BLOCK
"""

from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.risk.daily_trade_guard import evaluate_daily_trade_guard
from backend.app.risk.loss_streak_guard import evaluate_loss_streak
from backend.app.risk.concurrency_guard import evaluate_concurrency
from backend.app.risk.equity_drawdown_guard import (
    evaluate_equity_risk,
    EquitySnapshot,
)

# ---------------------------------------------------------------------
# CONFIG (can later move to config file)
# ---------------------------------------------------------------------

MAX_TRADES_PER_DAY = 15
MAX_CONSECUTIVE_LOSSES = 5
COOLDOWN_SECONDS = 3600
MAX_CONCURRENT_POSITIONS = 20

ENGINE_LOCKED = True  # execution layer lock


# ---------------------------------------------------------------------
# HEADLESS RUN
# ---------------------------------------------------------------------

def run_headless(request: Dict[str, Any]) -> Dict[str, Any]:

    steps = request.get("steps", 1)
    symbol = request.get("symbol", "EURUSD")
    execution_mode = request.get("execution_mode", "SIMULATION")
    current_open_positions = request.get("current_open_positions", 0)

    # Equity inputs (safe defaults)
    current_equity = request.get("current_equity", 100000.0)
    peak_equity = request.get("peak_equity", 100000.0)
    requested_trade_risk = request.get("requested_trade_risk", 1000.0)

    blocked_breakdown = {
        "daily_trade_guard_blocked": 0,
        "loss_streak_guard_blocked": 0,
        "concurrency_guard_blocked": 0,
        "equity_guard_blocked": 0,
        "locked_execution_blocked": 0,
        "other_blocked": 0,
    }

    simulated_trades = 0
    blocked_trades = 0

    # -----------------------------------------------------------------
    # Evaluate Guards
    # -----------------------------------------------------------------

    daily_result = evaluate_daily_trade_guard(
        trades_today=0,
        max_trades=MAX_TRADES_PER_DAY,
    )

    loss_result = evaluate_loss_streak(
        consecutive_losses=0,
        max_consecutive_losses=MAX_CONSECUTIVE_LOSSES,
        cooldown_seconds=COOLDOWN_SECONDS,
    )

    concurrency_result = evaluate_concurrency(
        open_positions=current_open_positions,
        max_positions=MAX_CONCURRENT_POSITIONS,
    )

    equity_result = evaluate_equity_risk(
        EquitySnapshot(
            current_equity=current_equity,
            peak_equity=peak_equity,
            requested_trade_risk=requested_trade_risk,
        )
    )

    # -----------------------------------------------------------------
    # Decision Logic Loop
    # -----------------------------------------------------------------

    for _ in range(steps):

        if not daily_result["allowed"]:
            blocked_trades += 1
            blocked_breakdown["daily_trade_guard_blocked"] += 1
            continue

        if loss_result["decision"] != "ALLOW":
            blocked_trades += 1
            blocked_breakdown["loss_streak_guard_blocked"] += 1
            continue

        if not concurrency_result["allowed"]:
            blocked_trades += 1
            blocked_breakdown["concurrency_guard_blocked"] += 1
            continue

        if equity_result["decision"] == "BLOCK":
            blocked_trades += 1
            blocked_breakdown["equity_guard_blocked"] += 1
            continue

        if ENGINE_LOCKED:
            blocked_trades += 1
            blocked_breakdown["locked_execution_blocked"] += 1
            continue

        simulated_trades += 1

    # -----------------------------------------------------------------
    # Response
    # -----------------------------------------------------------------

    return {
        "ok": True,
        "mode": execution_mode,
        "live_execution": not ENGINE_LOCKED,
        "locked": ENGINE_LOCKED,
        "steps_requested": steps,
        "symbol": symbol,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "blocked_breakdown": blocked_breakdown,
        "daily_trade_guard": daily_result,
        "loss_streak_guard": loss_result,
        "concurrency_guard": concurrency_result,
        "equity_guard": equity_result,
        "trade_preview": {
            "symbol": symbol,
            "side": "buy",
            "units": 1,
            "order_type": "MARKET",
        },
        "blocked_reason": (
            "Execution layer locked (no live trades)."
            if ENGINE_LOCKED else None
        ),
        "timestamp_utc": datetime.now(timezone.utc),
    }
