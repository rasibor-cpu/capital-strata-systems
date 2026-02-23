"""
tools/run_drawdown_stress.py

Full Institutional Drawdown Stress
----------------------------------

Evaluates:
- Max drawdown
- % drawdown
- Longest losing streak
- Worst 20-trade cluster
- Equity volatility
- Ulcer index

Research-only.
"""

from __future__ import annotations

import json
import argparse
import numpy as np


def compute_drawdown(equity_curve):
    peak = equity_curve[0]
    max_dd = 0.0
    dd_series = []

    for e in equity_curve:
        if e > peak:
            peak = e
        dd = peak - e
        dd_series.append(dd)
        if dd > max_dd:
            max_dd = dd

    return max_dd, dd_series


def longest_losing_streak(pnls):
    streak = 0
    max_streak = 0
    for p in pnls:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def worst_rolling_cluster(pnls, window=20):
    if len(pnls) < window:
        return sum(pnls)
    worst = float("inf")
    for i in range(len(pnls) - window + 1):
        cluster = sum(pnls[i:i+window])
        worst = min(worst, cluster)
    return worst


def ulcer_index(equity_curve):
    peak = equity_curve[0]
    squares = []
    for e in equity_curve:
        if e > peak:
            peak = e
        drawdown_pct = (peak - e) / peak
        squares.append(drawdown_pct ** 2)
    return np.sqrt(np.mean(squares))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    args = parser.parse_args()

    with open(args.json, "r") as f:
        data = json.load(f)

    # We reconstruct approximate equity curve
    # NOTE: replay summary stores only totals, so we approximate
    # from decile trade counts & avg pnl per trade

    pnls = []
    for d in data["decile_expectancy"]:
        trades = d["trades"]
        avg = d["avg_pnl_per_trade"]
        pnls.extend([avg] * trades)

    equity = 1000.0
    equity_curve = [equity]

    for p in pnls:
        equity += p
        equity_curve.append(equity)

    max_dd, dd_series = compute_drawdown(equity_curve)
    max_dd_pct = max_dd / max(equity_curve)

    streak = longest_losing_streak(pnls)
    worst_cluster = worst_rolling_cluster(pnls, window=20)
    vol = np.std(pnls)
    ui = ulcer_index(equity_curve)

    print("\n=== DRAWdown STRESS REPORT ===\n")
    print("Max Drawdown:", round(max_dd, 4))
    print("Max Drawdown %:", round(max_dd_pct * 100, 2), "%")
    print("Longest Losing Streak:", streak)
    print("Worst 20-trade cluster:", round(worst_cluster, 4))
    print("Trade PnL Std Dev:", round(vol, 6))
    print("Ulcer Index:", round(ui, 6))


if __name__ == "__main__":
    main()