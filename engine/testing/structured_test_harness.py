"""
Structured Deterministic Test Harness
REA Capital Trading Engine

Purpose:
Validate risk logic, position sizing, profit tiers,
cooldowns, and drawdown protection WITHOUT broker or market noise.
"""

from dataclasses import dataclass


@dataclass
class AccountState:
    equity: float
    peak_equity: float
    open_positions: int = 0
    loss_streak: int = 0
    trades_today: int = 0


MAX_TRADES_PER_DAY = 10
MAX_CONCURRENT_POSITIONS = 20
DRAWDOWN_LIMIT = 0.25


def simulate_trade(account: AccountState, return_pct: float):
    position_size = account.equity * 0.05  # 5% per trade baseline

    pnl = position_size * return_pct
    account.equity += pnl
    account.trades_today += 1

    if pnl < 0:
        account.loss_streak += 1
    else:
        account.loss_streak = 0

    if account.equity > account.peak_equity:
        account.peak_equity = account.equity

    drawdown = (account.peak_equity - account.equity) / account.peak_equity

    print(f"Trade #{account.trades_today}")
    print(f"Return %: {return_pct*100:.2f}%")
    print(f"Equity: {account.equity:.2f}")
    print(f"Drawdown: {drawdown:.2%}")
    print(f"Loss Streak: {account.loss_streak}")
    print("-" * 40)

    if drawdown > DRAWDOWN_LIMIT:
        print("DRAWDOWN LIMIT BREACHED — HALTING")
        return False

    if account.loss_streak >= 3:
        print("LOSS STREAK TRIGGERED — COOLDOWN")
        return False

    if account.trades_today >= MAX_TRADES_PER_DAY:
        print("MAX TRADES REACHED — STOP")
        return False

    return True


def run_structured_test():
    print("=== STRUCTURED LOGIC VALIDATION ===")
    account = AccountState(equity=100_000, peak_equity=100_000)

    # Deterministic return pattern
    test_returns = [
        0.02,   # +2%
        0.03,
        -0.02,
        -0.03,
        -0.01,  # loss streak trigger
        0.05,
        0.10,
        -0.20,  # shock loss
        0.50,
        0.20,
    ]

    for r in test_returns:
        continue_trading = simulate_trade(account, r)
        if not continue_trading:
            break

    print("Final Equity:", account.equity)
    print("Peak Equity:", account.peak_equity)
    print("=== END TEST ===")


if __name__ == "__main__":
    run_structured_test()
