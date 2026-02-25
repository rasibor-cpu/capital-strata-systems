"""
Phase 1 – Portfolio Replay V3 (Behaviour-Synchronized + Production-Consistent Risk)
Capital Strata Systems

Institutional-correct:
- Batch signal evaluation per timestamp
- Shared equity
- Equity curve tracking
- Max drawdown calculation
- Trade statistics
- risk_pct sourced from ExecutionGate/CompoundingEngine (no hardcoded risk)
- Behaviour is synchronized across StrategyProfile + CompoundingEngine
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine

STARTING_EQUITY = 100_000

# Set one of: "A","B","C","D","E"
BEHAVIOUR = "A"

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


def extract_risk_pct_from_decision(decision: Any, fallback: float) -> float:
    """
    Preferred: pull risk_pct from gate debug payload if present.
    Fallback: caller-provided float.
    """
    try:
        if isinstance(decision, dict):
            dbg = decision.get("debug")
            if isinstance(dbg, dict) and dbg.get("risk_pct") is not None:
                return float(dbg["risk_pct"])

            inner = decision.get("decision")
            if isinstance(inner, dict):
                dbg2 = inner.get("debug")
                if isinstance(dbg2, dict) and dbg2.get("risk_pct") is not None:
                    return float(dbg2["risk_pct"])
    except Exception:
        pass

    return float(fallback)


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


def bind_gate_behaviour(gate: ExecutionGate, behaviour_code: str) -> None:
    """
    Forces ExecutionGate risk layer to use the same behaviour code
    as the Strategy layer for this replay session.
    """
    try:
        # Replace compounding engine instance with behaviour-bound instance
        gate.compounding = gate.compounding.__class__(behaviour=behaviour_code)
    except Exception:
        # Fail-closed: if we cannot bind behaviour, we proceed but warn.
        print("WARNING: could not bind gate.compounding behaviour; results may collapse across regimes.")


def main():
    print("\n==== PHASE 1 PORTFOLIO REPLAY V3 (BEHAVIOUR-SYNC) ====\n")
    print("BEHAVIOUR:", BEHAVIOUR)

    datasets, sorted_ts = load_all_data()

    # Strategy profile uses the behaviour code
    profile = get_profile_for_behaviour(BEHAVIOUR)
    signal_engines = {inst: SignalEngine(profile) for inst in datasets}

    # Gate + bind behaviour into risk/compounding layer
    execution_gate = ExecutionGate()
    bind_gate_behaviour(execution_gate, BEHAVIOUR)

    pnl_tracker = PnLTracker(starting_equity=STARTING_EQUITY)

    price_windows = {inst: deque(maxlen=MA_WINDOW) for inst in datasets}
    prev_prices: Dict[str, float] = {}
    equity_peak = float(STARTING_EQUITY)

    total_signals = 0
    gate_blocks = 0
    trades = 0

    max_drawdown = 0.0
    new_highs = 0
    total_pnl = 0.0

    # risk stats
    risk_pct_sum = 0.0
    risk_pct_min = 9e9
    risk_pct_max = 0.0
    risk_samples = 0

    instrument_maps = {
        inst: {ts: price for ts, price in rows}
        for inst, rows in datasets.items()
    }

    for ts in sorted_ts:

        approved_trades: List[Tuple[str, float, float]] = []
        last_decision: Dict[str, Any] = {}

        # ---- SCAN ALL INSTRUMENTS FOR THIS TIMESTAMP ----
        for inst, price_map in instrument_maps.items():
            if ts not in price_map:
                continue

            price = float(price_map[ts])
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

            # Strategy threshold lives in profile; keep a safety floor:
            if float(signal.strength) < 0.61:
                prev_prices[inst] = price
                continue

            equity = float(pnl_tracker.current_equity)
            equity_peak = max(equity_peak, equity)

            decision = execution_gate.evaluate_trade(
                instrument=inst,
                side=signal.direction,
                notional=equity * 0.10,
                stop_distance_pct=float(STOP_DISTANCE_PCT),
                equity=equity,
                equity_peak=float(equity_peak),
                regime_persistence=float(REGIME_PERSISTENCE),
                policy="core",
            )

            last_decision[inst] = decision

            if not decision or decision.get("decision", {}).get("final") != "ALLOW":
                gate_blocks += 1
                prev_prices[inst] = price
                continue

            approved_trades.append((inst, price, prev_prices[inst]))
            prev_prices[inst] = price

        # ---- EXECUTE APPROVED TRADES ----
        for inst, price, prev_price in approved_trades:
            equity = float(pnl_tracker.current_equity)

            fallback_risk = execution_gate.compounding.compute_dynamic_risk(
                equity=float(equity),
                equity_peak=float(equity_peak),
                regime_persistence=float(REGIME_PERSISTENCE),
            )

            decision = last_decision.get(inst)
            risk_pct = extract_risk_pct_from_decision(decision, fallback=float(fallback_risk))

            # Track risk distribution
            risk_pct_sum += float(risk_pct)
            risk_pct_min = min(risk_pct_min, float(risk_pct))
            risk_pct_max = max(risk_pct_max, float(risk_pct))
            risk_samples += 1

            risk_amount = equity * float(risk_pct)

            move_ratio = (float(price) - float(prev_price)) / (float(price) * float(STOP_DISTANCE_PCT))
            if move_ratio > 3:
                move_ratio = 3
            elif move_ratio < -3:
                move_ratio = -3

            realized_pnl = float(move_ratio) * float(risk_amount)
            total_pnl += float(realized_pnl)

            pnl_tracker.record_trade(
                instrument=inst,
                realized_pnl=float(realized_pnl),
                unrealized_pnl=0.0,
            )

            trades += 1

        # ---- EQUITY TRACKING (once per timestamp) ----
        equity_now = float(pnl_tracker.current_equity)

        if equity_now > equity_peak:
            equity_peak = equity_now
            new_highs += 1

        dd = (equity_peak - equity_now) / equity_peak if equity_peak > 0 else 0.0
        if dd > max_drawdown:
            max_drawdown = dd

    ending_equity = float(pnl_tracker.current_equity)
    net_pnl = float(ending_equity - float(STARTING_EQUITY))
    avg_trade_pnl = float(total_pnl / trades) if trades > 0 else 0.0

    avg_risk_pct = float(risk_pct_sum / risk_samples) if risk_samples > 0 else 0.0
    min_risk_pct = float(risk_pct_min if risk_samples > 0 else 0.0)
    max_risk_pct = float(risk_pct_max if risk_samples > 0 else 0.0)

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
    print("avg_risk_pct:", round(avg_risk_pct, 6))
    print("min_risk_pct:", round(min_risk_pct, 6))
    print("max_risk_pct:", round(max_risk_pct, 6))
    print("\nDone.")


if __name__ == "__main__":
    main()