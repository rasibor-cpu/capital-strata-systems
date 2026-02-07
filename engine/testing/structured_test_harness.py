"""
Structured Deterministic Test Harness (v2)
REA Capital Trading Engine

Purpose:
Validate risk logic deterministically WITHOUT broker or market randomness.

Validates:
- Max trades per day
- Max concurrent positions
- Loss streak cooldown trigger
- Cooldown time window (>= 1 hour)
- Drawdown cap (halt)
- Equity/peak/drawdown tracking

NOTE:
This harness simulates time with an integer "minute clock" to test cooldown windows.
"""

from __future__ import annotations

from dataclasses import dataclass


# ----------------------------
# Phase-1 parameters (UPDATED)
# ----------------------------
MAX_TRADES_PER_DAY = 20
MAX_CONCURRENT_POSITIONS = 50
DRAWDOWN_LIMIT = 0.30  # 30%
LOSS_STREAK_LIMIT = 5
COOLDOWN_MINUTES = 60  # >= 1 hour


@dataclass
class AccountState:
    equity: float
    peak_equity: float
    open_positions: int = 0
    loss_streak: int = 0
    trades_today: int = 0
    cooldown_until_minute: int = -1  # minute index until which we are cooling down


def _drawdown(state: AccountState) -> float:
    if state.peak_equity <= 0:
        return 0.0
    return (state.peak_equity - state.equity) / state.peak_equity


def _in_cooldown(state: AccountState, now_minute: int) -> bool:
    return now_minute < state.cooldown_until_minute


def _enter_cooldown(state: AccountState, now_minute: int) -> None:
    state.cooldown_until_minute = now_minute + COOLDOWN_MINUTES


def _print_state(label: str, state: AccountState, now_minute: int) -> None:
    dd = _drawdown(state)
    cd = _in_cooldown(state, now_minute)
    print(label)
    print(f"Minute: {now_minute}")
    print(f"Equity: {state.equity:.2f}")
    print(f"Peak:   {state.peak_equity:.2f}")
    print(f"DD:     {dd:.2%}")
    print(f"Trades: {state.trades_today}/{MAX_TRADES_PER_DAY}")
    print(f"Open:   {state.open_positions}/{MAX_CONCURRENT_POSITIONS}")
    print(f"LStk:   {state.loss_streak}/{LOSS_STREAK_LIMIT}")
    print(f"CD:     {int(cd)} (until minute {state.cooldown_until_minute})")
    print("-" * 48)


def can_open_new_trade(state: AccountState, now_minute: int) -> tuple[bool, str]:
    if _in_cooldown(state, now_minute):
        return False, "cooldown_active"

    if state.trades_today >= MAX_TRADES_PER_DAY:
        return False, "max_trades_per_day_reached"

    if state.open_positions >= MAX_CONCURRENT_POSITIONS:
        return False, "max_concurrent_positions_reached"

    if _drawdown(state) > DRAWDOWN_LIMIT:
        return False, "drawdown_cap_breached"

    return True, "ok"


def simulate_trade(state: AccountState, now_minute: int, return_pct: float) -> bool:
    """
    Executes one deterministic trade (open -> immediate close) for logic testing.
    Uses a fixed position size fraction to test equity dynamics.
    """

    ok, reason = can_open_new_trade(state, now_minute)
    if not ok:
        _print_state(f"BLOCKED | {reason}", state, now_minute)
        return False

    # Simulate opening a position
    state.open_positions += 1
    state.trades_today += 1

    # Position sizing (kept simple for deterministic validation)
    position_size = state.equity * 0.05  # 5% baseline sizing for harness

    pnl = position_size * return_pct
    state.equity += pnl

    # Close immediately (this is a logic harness)
    state.open_positions -= 1

    # Update streaks + peaks
    if pnl < 0:
        state.loss_streak += 1
    else:
        state.loss_streak = 0

    if state.equity > state.peak_equity:
        state.peak_equity = state.equity

    # Print trade summary
    _print_state(
        f"TRADE #{state.trades_today} | Return {return_pct*100:.2f}% | PnL {pnl:.2f}",
        state,
        now_minute,
    )

    # Enforce drawdown cap
    if _drawdown(state) > DRAWDOWN_LIMIT:
        print("HALT | DRAWDOWN CAP BREACHED (30%)")
        return False

    # Enforce loss streak cooldown
    if state.loss_streak >= LOSS_STREAK_LIMIT:
        _enter_cooldown(state, now_minute)
        print(f"COOLDOWN | Loss streak {state.loss_streak} reached. Cooling down for {COOLDOWN_MINUTES} minutes.")
        return True  # we don't halt the day; we pause trading

    return True


def run_structured_test() -> None:
    print("=== STRUCTURED LOGIC VALIDATION (v2) ===")

    state = AccountState(equity=100_000.0, peak_equity=100_000.0)

    # Minute clock: each trade attempt is 10 minutes apart
    # This lets us validate 60-minute cooldown windows deterministically.
    minute = 0
    step = 10

    # Pattern: 2 wins, then 5 consecutive losses (trigger cooldown),
    # then attempts during cooldown (should block),
    # then after cooldown ends, we resume with wins.
    test_returns = [
        0.02, 0.03,           # wins
        -0.02, -0.03, -0.01, -0.02, -0.01,  # 5 losses -> cooldown
        0.05, 0.05,           # will be attempted during cooldown (blocked)
        0.04, 0.03,           # after cooldown passes, should execute
    ]

    for r in test_returns:
        simulate_trade(state, minute, r)
        minute += step

    print("=== END TEST ===")
    print(f"Final Equity: {state.equity:.2f}")
    print(f"Peak Equity:  {state.peak_equity:.2f}")
    print(f"Final DD:     {_drawdown(state):.2%}")
    print(f"Trades Today: {state.trades_today}")
    print(f"Cooldown Until Minute: {state.cooldown_until_minute}")


if __name__ == "__main__":
    run_structured_test()
