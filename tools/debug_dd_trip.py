"""
Debug Drawdown Trip Analyzer (SAFE)
Capital Strata Systems

Uses the real SignalEngine.generate signature:
  generate(instrument, price_now, price_prev, moving_avg)

Goal:
- Identify first N times ExecutionGate blocks with hard_drawdown_limit_reached
- Print bar index + price context when it starts happening

NOTE:
This is a gate-decision tracer. Equity/peak printing must be done in the
governance runner context (next step) because that's where equity is bound.
"""

import pandas as pd

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.signal_engine import SignalEngine
from engine.strategy.strategy_mode import StrategyProfile


CSV_PATH = "data/history/GBP_USD_M5_1year.csv"
INSTRUMENT = "GBP_USD"
MIN_SIG = 0.80
MAX_ROWS = 30000         # widen window to ensure we see the trip
MAX_TRIPS = 10
MA_WINDOW = 20


def make_profile(min_sig: float) -> StrategyProfile:
    # Required positional signature in your codebase
    return StrategyProfile(
        "DEBUG_BALANCED",          # name
        "Debug profile",           # description
        10_000_000,                # max_trades_per_week (effectively off)
        True,                      # allow_trend
        True,                      # allow_mean_reversion
        1.0,                       # risk_bias_multiplier
        float(min_sig),            # min_signal_strength
    )


def main():
    print("Loading CSV...")
    df = pd.read_csv(CSV_PATH).head(MAX_ROWS)

    if "price" not in df.columns:
        raise ValueError("CSV must contain column: price")

    prices = df["price"].astype(float).tolist()

    profile = make_profile(MIN_SIG)
    signal_engine = SignalEngine(profile)
    gate = ExecutionGate()

    trips = 0
    print("Running debug replay...")

    # Precompute simple moving average for the same price stream
    s = pd.Series(prices)
    ma = s.rolling(MA_WINDOW).mean().tolist()

    for i in range(1, len(prices)):
        price_now = float(prices[i])
        price_prev = float(prices[i - 1])

        moving_avg = ma[i]
        if moving_avg != moving_avg:  # NaN check
            moving_avg = price_prev   # fallback until MA is ready

        sig_obj = signal_engine.generate(
            INSTRUMENT,
            price_now,
            price_prev,
            float(moving_avg),
        )

        decision = gate.validate_trade(
            instrument=INSTRUMENT,
            signal=sig_obj,
            requested_notional=1.0,
        )

        if (not decision.ok) and getattr(decision, "reason", "") == "hard_drawdown_limit_reached":
            print(f"\n--- HARD DD TRIP #{trips + 1} ---")
            print(f"bar_index: {i}")
            print(f"price_prev: {price_prev}")
            print(f"price_now:  {price_now}")
            print(f"moving_avg: {moving_avg}")
            print(f"status: {getattr(decision, 'status', None)}")
            print(f"reason:  {getattr(decision, 'reason', None)}")
            print(f"recommended_notional: {getattr(decision, 'recommended_notional', None)}")
            trips += 1
            if trips >= MAX_TRIPS:
                break

    print("\nDebug complete.")
    if trips == 0:
        print("No hard drawdown trips observed in this window.")
        print("If governance_deciles still blocks, the trip is equity-binding specific.")


if __name__ == "__main__":
    main()