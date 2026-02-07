"""
Edge Report Tool (Phase-1 Risk Validation)
------------------------------------------

Computes:
- Win rate
- Avg win
- Avg loss
- Profit factor
- Expectancy per trade
- Max drawdown (equity curve based)
- Net PnL
- Total fees

Reads from:
    pnl_ledger_test.jsonl
    pnl_ledger_live.jsonl
"""

import json
import argparse
from pathlib import Path
from statistics import mean


def load_ledger(path: Path):
    if not path.exists():
        print("Ledger not found:", path)
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def compute_metrics(rows):
    if not rows:
        return {}

    pnls = [r["pnl"] for r in rows]
    fees = [r.get("fees", 0.0) for r in rows]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    equity_curve = []
    running = 0
    peak = 0
    max_dd = 0

    for p in pnls:
        running += p
        equity_curve.append(running)
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)

    total_trades = len(pnls)
    win_rate = (len(wins) / total_trades) * 100 if total_trades else 0

    avg_win = mean(wins) if wins else 0
    avg_loss = mean(losses) if losses else 0

    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    return {
        "trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "gross_win": gross_win,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "max_drawdown": max_dd,
        "net_pnl": sum(pnls),
        "total_fees": sum(fees),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="TEST", choices=["TEST", "LIVE"])
    args = parser.parse_args()

    filename = (
        "pnl_ledger_test.jsonl"
        if args.mode == "TEST"
        else "pnl_ledger_live.jsonl"
    )

    ledger_path = Path("reporting_store") / filename
    rows = load_ledger(ledger_path)
    stats = compute_metrics(rows)

    if not stats:
        print("No trades found.")
        return

    print("\n=== EDGE REPORT [{}] ===".format(args.mode))
    print("Trades:", stats["trades"])
    print("Wins:", stats["wins"])
    print("Losses:", stats["losses"])
    print("Win rate: {:.2f}%".format(stats["win_rate"]))
    print("Avg Win: {:.2f}".format(stats["avg_win"]))
    print("Avg Loss: {:.2f}".format(stats["avg_loss"]))
    print("Profit Factor: {:.2f}".format(stats["profit_factor"]))
    print("Expectancy per trade: {:.2f}".format(stats["expectancy"]))
    print("Max Drawdown: {:.2f}".format(stats["max_drawdown"]))
    print("Net PnL: {:.2f}".format(stats["net_pnl"]))
    print("Total Fees: {:.2f}".format(stats["total_fees"]))
    print()


if __name__ == "__main__":
    main()
