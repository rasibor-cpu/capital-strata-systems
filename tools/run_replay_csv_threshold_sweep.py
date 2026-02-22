"""
tools/run_replay_csv_threshold_sweep.py

Replay runner with:
- Threshold gating
- PnL summary
- Strength–Expectancy Decile Analysis (Equal Population)

Replay-only research layer.
No live trading impact.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from statistics import mean
from typing import List, Tuple

from engine.strategy.signal_engine import SignalEngine
from engine.strategy.strategy_mode import StrategyProfile


# ============================================================
# DECILE ANALYSIS
# ============================================================

def compute_deciles(strength_pnl: List[Tuple[float, float]]) -> List[dict]:
    if not strength_pnl:
        return []

    # Sort by strength ascending
    strength_pnl.sort(key=lambda x: x[0])

    n = len(strength_pnl)
    bucket_size = max(1, n // 10)

    deciles = []

    for i in range(10):
        start = i * bucket_size
        end = (i + 1) * bucket_size if i < 9 else n

        bucket = strength_pnl[start:end]
        if not bucket:
            continue

        strengths = [x[0] for x in bucket]
        pnls = [x[1] for x in bucket]

        trades = len(bucket)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)

        avg_pnl = mean(pnls)
        win_rate = wins / trades if trades > 0 else 0.0
        total_pnl = sum(pnls)

        deciles.append({
            "decile": i + 1,
            "strength_min": min(strengths),
            "strength_max": max(strengths),
            "trades": trades,
            "win_rate": round(win_rate, 4),
            "avg_pnl_per_trade": round(avg_pnl, 6),
            "total_pnl": round(total_pnl, 6)
        })

    return deciles


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--minsig", type=float, required=True)
    parser.add_argument("--behaviour", default="C")

    args = parser.parse_args()

    profile = StrategyProfile(mode=args.behaviour)
    engine = SignalEngine(profile)

    strength_pnl_records: List[Tuple[float, float]] = []

    equity = 1000.0
    starting_equity = equity

    total_signals = 0
    threshold_blocks = 0
    trades = 0

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)

        prev_price = None

        for row in reader:
            price = float(row["price"])

            if prev_price is None:
                prev_price = price
                continue

            moving_avg = price  # Simplified MA proxy

            signal = engine.generate(
                instrument=args.instrument,
                price_now=price,
                price_prev=prev_price,
                moving_avg=moving_avg
            )

            total_signals += 1

            if signal.strength < args.minsig:
                threshold_blocks += 1
                prev_price = price
                continue

            # Simplified PnL model (directional 1-bar hold)
            direction = signal.direction
            pnl = 0.0

            if direction == "BUY":
                pnl = price - prev_price
            elif direction == "SELL":
                pnl = prev_price - price

            equity += pnl
            trades += 1

            strength_pnl_records.append((signal.strength, pnl))

            prev_price = price

    net_pnl = equity - starting_equity

    decile_stats = compute_deciles(strength_pnl_records)

    summary = {
        "min_signal_strength": args.minsig,
        "total_signals": total_signals,
        "threshold_blocks": threshold_blocks,
        "trades": trades,
        "starting_equity": starting_equity,
        "ending_equity": equity,
        "net_pnl": net_pnl,
        "decile_expectancy": decile_stats,
        "run_utc": datetime.now(timezone.utc).isoformat()
    }

    print("\n=== CSS DECILE EXPECTANCY ANALYSIS ===\n")
    for d in decile_stats:
        print(d)

    print("\n=== CSS REPLAY SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()