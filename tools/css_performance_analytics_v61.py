"""
CSS Performance Analytics Engine v61
Analyzes trade performance from audit_logs/trades.jsonl
"""

import json
from pathlib import Path
from statistics import mean

TRADES_FILE = Path("audit_logs/trades.jsonl")


def load_trades():
    trades = []

    if not TRADES_FILE.exists():
        return trades

    with open(TRADES_FILE, "r") as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except:
                pass

    return trades


def extract_realized_pnls(trades):
    pnls = []

    for t in trades:
        if t.get("type") == "SELL":
            pnl = t.get("pnl")
            if pnl is not None:
                pnls.append(float(pnl))

    return pnls


def compute_stats(pnls):

    total_trades = len(pnls)

    if total_trades == 0:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "total_pnl": 0,
        }

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)

    win_rate = len(wins) / total_trades * 100 if total_trades else 0

    avg_win = mean(wins) if wins else 0
    avg_loss = mean(losses) if losses else 0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float("inf")
    )

    return {
        "total": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
    }


def print_report(stats):

    print("\n")
    print("=" * 60)
    print("CAPITAL STRATA SYSTEMS — PERFORMANCE REPORT")
    print("=" * 60)

    print("\nTrade Statistics\n")

    print(f"Total Trades        : {stats['total']}")
    print(f"Wins                : {stats['wins']}")
    print(f"Losses              : {stats['losses']}")
    print(f"Win Rate            : {stats['win_rate']:.2f}%")

    print("\nProfit Metrics\n")

    print(f"Total Realized PnL  : {stats['total_pnl']:.2f}")
    print(f"Average Win         : {stats['avg_win']:.4f}")
    print(f"Average Loss        : {stats['avg_loss']:.4f}")
    print(f"Profit Factor       : {stats['profit_factor']:.4f}")

    print("\n")


def main():

    trades = load_trades()

    pnls = extract_realized_pnls(trades)

    stats = compute_stats(pnls)

    print_report(stats)


if __name__ == "__main__":
    main()