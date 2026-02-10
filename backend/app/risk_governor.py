from __future__ import annotations

from datetime import datetime, timedelta, timezone


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

MAX_TRADES_PER_DAY = 15
MAX_CONSECUTIVE_LOSSES = 5
MAX_DAILY_DRAWDOWN_PCT = 0.05
MAX_PEAK_DRAWDOWN_PCT = 0.20
COOLDOWN_MINUTES = 30


# --------------------------------------------------
# UTIL
# --------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc)


# --------------------------------------------------
# MAIN EVALUATOR
# --------------------------------------------------

def evaluate_risk(simulator, requested_size: float):

    state = simulator.risk_state()

    trades_today = state["trades_today"]
    daily_pnl = state["daily_pnl"]
    consecutive_losses = state["consecutive_losses"]
    equity = simulator.equity
    equity_peak = state["equity_peak"]

    # --------------------------------------------------
    # 1. TRADE COUNT LIMIT
    # --------------------------------------------------

    if trades_today >= MAX_TRADES_PER_DAY:
        return _block(
            "MAX_TRADES_PER_DAY_EXCEEDED",
            state
        )

    # --------------------------------------------------
    # 2. DAILY DRAWDOWN
    # --------------------------------------------------

    if daily_pnl <= -(simulator.starting_equity * MAX_DAILY_DRAWDOWN_PCT):
        return _block(
            "MAX_DAILY_DRAWDOWN_EXCEEDED",
            state
        )

    # --------------------------------------------------
    # 3. PEAK DRAWDOWN
    # --------------------------------------------------

    drawdown_pct = (equity - equity_peak) / equity_peak

    if drawdown_pct <= -MAX_PEAK_DRAWDOWN_PCT:
        return _block(
            "MAX_PEAK_DRAWDOWN_EXCEEDED",
            state
        )

    # --------------------------------------------------
    # 4. CONSECUTIVE LOSSES + COOLDOWN
    # --------------------------------------------------

    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:

        cooldown_until = _utc_now() + timedelta(minutes=COOLDOWN_MINUTES)

        simulator.cooldown_active = True
        simulator.cooldown_until = cooldown_until

        state["cooldown_active"] = True
        state["cooldown_until_utc"] = cooldown_until.isoformat()

        return _block(
            "MAX_CONSECUTIVE_LOSSES_EXCEEDED",
            state
        )

    # --------------------------------------------------
    # 5. FLOATING SIZE REDUCTION
    # --------------------------------------------------

    multiplier = 1.0

    current_drawdown = (equity - equity_peak) / equity_peak

    if current_drawdown <= -0.10:
        multiplier = 0.25
    elif current_drawdown <= -0.05:
        multiplier = 0.5

    adjusted_size = requested_size * multiplier

    return {
        "decision": "APPROVED",
        "reason": "Risk checks passed",
        "adjusted_size": adjusted_size,
        "multiplier": multiplier,
        "risk_state": state,
    }


# --------------------------------------------------
# BLOCK RESPONSE
# --------------------------------------------------

def _block(reason: str, state: dict):

    return {
        "decision": "BLOCKED",
        "reason": reason,
        "adjusted_size": 0,
        "multiplier": 0,
        "risk_state": state,
    }
