"""
Phase 1 – Portfolio Replay V2 (Time-Synchronized + Risk Metrics)
Capital Strata Systems

Institutional-correct:
- Batch signal evaluation per timestamp
- Shared equity
- Proper equity tracking
- Max drawdown calculation
- Trade statistics
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine

STARTING_EQUITY = 100_000
BEHAVIOUR = "D"
MA_WINDOW = 20
STOP_DISTANCE_PCT = 0.01
REGIME_PERSISTENCE = 0.95
PIP_SCALE = 10000.0

DATA_DIR = REPO_ROOT / "data" / "history"
PRICE_COLS = ["close", "price", "Close", "Price", "c"]


def detect_price_col(fields):
    for c in PRICE_COLS:
        if c in fields:
            return c
    return fields[-1]


def load_all_data():
    datasets = {}
    timestamps = set()

    for file in sorted(DATA_DIR.glob("*_M5_1year.csv")):
        instrument = file.stem.replace("_M5_1year", "").replace("_", "")
        with open(file, "r", newline="") as f:
            reader = csv.DictReader(f)
            price_col = detect_price_col(reader.fieldnames)
            rows = []
            for row in reader:
                ts = row["timestamp"]
                price = float(row[price_col])
                rows.append((ts, price))
                timestamps.add(ts)

        datasets[instrument] = rows

    sorted_ts = sorted(timestamps)
    return datasets, sorted_ts


def main():
    print("\n==== PHASE 1 PORTFOLIO REPLAY V2 ====\n")

    datasets, sorted_ts = load_all_data()

    profile = get_profile_for_behaviour(BEHAVIOUR)
    signal_engines = {inst: SignalEngine(profile) for inst in datasets}
    execution_gate = ExecutionGate()
    pnl_tracker = PnLTracker(starting_equity=STARTING_EQUITY)

    price_windows = {inst: deque(maxlen=MA_WINDOW) for inst in datasets}
    prev_prices: Dict[str, float] = {}
    equity_peak = STARTING_EQUITY

    total_signals = 0
    gate_blocks = 0
    trades = 0

    equity_curve = []
    max_drawdown = 0.0
    new_highs = 0
    total_pnl = 0.0

    instrument_maps = {
        inst: {ts: price for ts, price in rows}
        for inst, rows in datasets.items()
    }

    for ts in sorted_ts:

        approved_trades: List[Tuple[str, float, float]] = []

        for inst, price_map in instrument_maps.items():
            if ts not in price_map:
                continue

            price = price_map[ts]
            price_windows[inst].append(price)

            if inst not in prev_prices:
                prev_prices[inst] = price
                continue

            if len(price_windows[inst]) < MA_WINDOW:
                prev_prices[inst] = price
                continue

            moving_avg = sum(price_windows[inst]) / len(price_windows[inst])

            signal = signal_engines[inst].generate(
                instrument=inst,
                price_now=price,
                price_prev=prev_prices[inst],
                moving_avg=moving_avg,
            )

            total_signals += 1

            if signal.direction == "FLAT":
                prev_prices[inst] = price
                continue

            if signal.strength < 0.61:
                prev_prices[inst] = price
                continue

            equity = pnl_tracker.current_equity
            equity_peak = max(equity_peak, equity)

            decision = execution_gate.evaluate_trade(
                instrument=inst,
                side=signal.direction,
                notional=equity * 0.10,
                stop_distance_pct=STOP_DISTANCE_PCT,
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=REGIME_PERSISTENCE,
                policy="core",
            )

            if not decision or decision.get("decision", {}).get("final") != "ALLOW":
                gate_blocks += 1
                prev_prices[inst] = price
                continue

            approved_trades.append((inst, price, prev_prices[inst]))
            prev_prices[inst] = price

        # ---- EXECUTE APPROVED TRADES ----
        for inst, price, prev_price in approved_trades:
            equity = pnl_tracker.current_equity
            risk_pct = 0.008
            risk_amount = equity * risk_pct

            move_ratio = (price - prev_price) / (price * STOP_DISTANCE_PCT)

            if move_ratio > 3:
                move_ratio = 3
            elif move_ratio < -3:
                move_ratio = -3

            realized_pnl = move_ratio * risk_amount
            total_pnl += realized_pnl

            pnl_tracker.record_trade(
                instrument=inst,
                realized_pnl=realized_pnl,
                unrealized_pnl=0.0,
            )

            trades += 1

        # ---- EQUITY TRACKING ----
        equity_now = pnl_tracker.current_equity
        equity_curve.append(equity_now)

        if equity_now > equity_peak:
            equity_peak = equity_now
            new_highs += 1

        drawdown = (equity_peak - equity_now) / equity_peak if equity_peak > 0 else 0.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    ending_equity = pnl_tracker.current_equity
    net_pnl = ending_equity - STARTING_EQUITY
    avg_trade_pnl = total_pnl / trades if trades > 0 else 0.0

    print("Portfolio Summary:")
    print("total_signals:", total_signals)
    print("gate_blocks:", gate_blocks)
    print("trades:", trades)
    print("starting_equity:", STARTING_EQUITY)
    print("ending_equity:", ending_equity)
    print("net_pnl:", net_pnl)
    print("max_drawdown_pct:", round(max_drawdown * 100, 2))
    print("new_equity_highs:", new_highs)
    print("avg_trade_pnl:", round(avg_trade_pnl, 6))
    print("\nDone.")


if __name__ == "__main__":
    main()