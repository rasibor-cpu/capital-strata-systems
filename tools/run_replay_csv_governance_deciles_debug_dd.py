import sys
import argparse
import pandas as pd

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.signal_engine import SignalEngine
from engine.strategy.strategy_mode import StrategyProfile

MA_WINDOW = 20


def make_profile(min_sig: float) -> StrategyProfile:
    return StrategyProfile(
        "DD_DEBUG_BALANCED",
        "DD debug profile",
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
    p.add_argument("--policy", default="core")
    p.add_argument("--max-rows", type=int, default=50000)
    args = p.parse_args()

    print("Loading:", args.csv)
    df = pd.read_csv(args.csv).head(args.max_rows)

    prices = df["price"].astype(float).tolist()
    ts = df["timestamp"].tolist() if "timestamp" in df.columns else None

    prof = make_profile(args.minsig)
    se = SignalEngine(prof)
    gate = ExecutionGate()

    equity = 1000.0
    equity_peak = 1000.0

    s = pd.Series(prices)
    ma = s.rolling(MA_WINDOW).mean().tolist()

    notional = 1.0
    stop_distance_pct = 0.002
    regime_persistence = 0.5
    volatility_state = "MEDIUM"
    regime_state = "NORMAL"

    pip_scale = 10000.0
    equity_pnl_scale = 0.10

    for i in range(1, len(prices) - 1):
        price_now = float(prices[i])
        price_prev = float(prices[i - 1])

        moving_avg = ma[i]
        if moving_avg != moving_avg:
            moving_avg = price_prev

        sig = se.generate(args.instrument, price_now, price_prev, float(moving_avg))
        side = side_from_signal(sig)
        if side is None:
            continue

        strength = float(getattr(sig, "strength", 0.0))
        if strength < args.minsig:
            continue

        out = gate.evaluate_trade(
            instrument=args.instrument,
            side=side,
            notional=float(notional),
            stop_distance_pct=float(stop_distance_pct),
            equity=float(equity),
            equity_peak=float(equity_peak),
            regime_persistence=float(regime_persistence),
            policy=str(args.policy),
            current_allocations=None,
            rebalance_target_weights=None,
            volatility_state=str(volatility_state),
            regime_state=str(regime_state),
        )

        ok = bool(out.get("ok", False))
        reason = out.get("reason", "")

        if (not ok) and (reason == "hard_drawdown_limit_reached"):
            dd = (equity_peak - equity) / equity_peak if equity_peak else None
            print("\nHARD DD TRIGGER DETECTED")
            print("bar_index:", i)
            if ts:
                print("timestamp:", ts[i])
            print("equity:", equity)
            print("equity_peak:", equity_peak)
            print("computed_dd:", dd)
            print("gate_out:", out)
            sys.exit(0)

        if ok:
            price_next = float(prices[i + 1])
            direction = 1.0 if side == "LONG" else -1.0
            pnl_pips = direction * (price_next - price_now) * pip_scale
            equity += pnl_pips * equity_pnl_scale
            if equity > equity_peak:
                equity_peak = equity

    print("No hard DD trigger observed in this run window.")


if __name__ == "__main__":
    main()