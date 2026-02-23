"""
Governance Deciles – DD Tap (STRICT TRACKER VERSION)
----------------------------------------------------
Purpose:
Detect the FIRST hard_drawdown_limit_reached event
and print the exact equity + peak values being fed
into RiskGovernor via ExecutionGate.

This version uses your actual PnLTracker attributes:
- current_equity
- peak_equity
"""

import sys
import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.signal_engine import SignalEngine
from engine.strategy.strategy_mode import StrategyProfile


MA_WINDOW = 20


def make_profile(min_sig: float) -> StrategyProfile:
    return StrategyProfile(
        "DD_TAP_BALANCED",
        "DD tap profile",
        10_000_000,
        True,
        True,
        1.0,
        float(min_sig),
    )


def side_from_signal(sig):
    d = getattr(sig, "direction", None)
    if d == "BUY":
        return "LONG"
    if d == "SELL":
        return "SHORT"
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--instrument", required=True)
    p.add_argument("--minsig", type=float, required=True)
    p.add_argument("--policy", default="BALANCED")
    p.add_argument("--max-rows", type=int, default=300000)
    args = p.parse_args()

    print("Loading:", args.csv)
    df = pd.read_csv(args.csv).head(args.max_rows)

    if "price" not in df.columns:
        raise ValueError("CSV must contain column: price")

    prices = df["price"].astype(float).tolist()
    ts = df["timestamp"].tolist() if "timestamp" in df.columns else None

    profile = make_profile(args.minsig)
    signal_engine = SignalEngine(profile)
    gate = ExecutionGate()

    # Your real tracker structure
    tracker = PnLTracker(1000.0)

    s = pd.Series(prices)
    ma = s.rolling(MA_WINDOW).mean().tolist()

    notional = 1.0
    stop_distance_pct = 0.002
    regime_persistence = 0.5
    volatility_state = "MEDIUM"
    regime_state = "NORMAL"

    gate_block_reasons = {}

    for i in range(1, len(prices) - 1):
        price_now = float(prices[i])
        price_prev = float(prices[i - 1])

        moving_avg = ma[i]
        if moving_avg != moving_avg:
            moving_avg = price_prev

        sig = signal_engine.generate(
            args.instrument,
            price_now,
            price_prev,
            float(moving_avg),
        )

        side = side_from_signal(sig)
        if side is None:
            continue

        strength = float(getattr(sig, "strength", 0.0))
        if strength < args.minsig:
            continue

        # Use YOUR tracker fields directly
        eq = float(tracker.current_equity)
        pk = float(tracker.peak_equity)
        dd = (pk - eq) / pk if pk else None

        out = gate.evaluate_trade(
            instrument=args.instrument,
            side=side,
            notional=float(notional),
            stop_distance_pct=float(stop_distance_pct),
            equity=eq,
            equity_peak=pk,
            regime_persistence=float(regime_persistence),
            policy=str(args.policy),
            current_allocations=None,
            rebalance_target_weights=None,
            volatility_state=str(volatility_state),
            regime_state=str(regime_state),
        )

        ok = bool(out.get("ok", False))
        reason = out.get("reason", "")

        if not ok:
            gate_block_reasons[reason] = gate_block_reasons.get(reason, 0) + 1

        if (not ok) and (reason == "hard_drawdown_limit_reached"):
            print("\n============================")
            print("DD TAP: FIRST HARD DD BLOCK")
            print("============================")
            print("bar_index:", i)
            if ts:
                print("timestamp:", ts[i])
            print("price_now:", price_now)
            print("equity:", eq)
            print("equity_peak:", pk)
            print("computed_dd:", dd)
            print("gate_out:", out)
            print("gate_block_reasons_so_far:", json.dumps(gate_block_reasons, indent=2))
            print("run_utc:", datetime.now(timezone.utc).isoformat())
            print("============================\n")
            sys.exit(0)

    print("No hard DD block observed.")
    print("gate_block_reasons:", json.dumps(gate_block_reasons, indent=2))


if __name__ == "__main__":
    main()