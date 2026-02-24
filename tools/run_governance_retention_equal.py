"""
tools/run_governance_retention_equal.py

CSS – Alpha Sanity + Hold-Period Robustness Harness (Step 1B)
------------------------------------------------------------
Runs ALPHA-only expectancy using your SignalEngine.generate() signature:

    generate(instrument, price_now, price_prev, moving_avg)

Key upgrades:
- Adds --hold N  (N-bar holding period)
- Keeps equal-notional PnL
- Uses SMA(window) as moving_avg baseline (default 20)
- Writes JSON to audit_logs/governance_retention_equal/

Next step after this:
- Add governance pass + compute GRM once we have a hold that shows edge (or at least less negative).
"""

from __future__ import annotations

import sys
from pathlib import Path
import argparse
import csv
import json
from statistics import mean
from typing import List, Optional

# Ensure repo root is visible for engine.* imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.strategy.strategy_mode import StrategyProfile
from engine.strategy.signal_engine import SignalEngine


def load_prices(csv_path: Path) -> List[float]:
    prices: List[float] = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = None
            if "close" in row and row["close"] not in (None, ""):
                raw = row["close"]
            elif "Close" in row and row["Close"] not in (None, ""):
                raw = row["Close"]
            elif "price" in row and row["price"] not in (None, ""):
                raw = row["price"]

            if raw is None:
                continue

            try:
                prices.append(float(raw))
            except Exception:
                continue
    return prices


def sma(prices: List[float], window: int, i: int) -> Optional[float]:
    if i < window:
        return None
    return sum(prices[i - window : i]) / window


def summarize(pnls: List[float]) -> dict:
    if not pnls:
        return {"trades": 0, "expectancy": 0.0, "winrate": 0.0, "total_pnl": 0.0}
    wins = [p for p in pnls if p > 0]
    return {
        "trades": len(pnls),
        "expectancy": float(mean(pnls)),
        "winrate": float(len(wins) / len(pnls)),
        "total_pnl": float(sum(pnls)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to CSV dataset")
    parser.add_argument("--instrument", default="GBP_USD", help="Instrument symbol")
    parser.add_argument("--minsig", type=float, default=0.61, help="Min signal strength filter")
    parser.add_argument("--ma_window", type=int, default=20, help="SMA window used for moving_avg")
    parser.add_argument("--hold", type=int, default=1, help="Holding period in bars (e.g., 1,3,5,10)")
    args = parser.parse_args()

    if args.hold < 1:
        raise ValueError("--hold must be >= 1")

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    prices = load_prices(csv_path)

    print(f"\nCSV: {csv_path}")
    print(f"Prices loaded: {len(prices)}")
    print(f"Instrument: {args.instrument}")
    print(f"minsig: {args.minsig:.2f}")
    print(f"MA window: {args.ma_window}")
    print(f"Hold (bars): {args.hold}")

    if len(prices) < args.ma_window + args.hold + 5:
        raise ValueError("Not enough price rows for MA window + hold period.")

    # StrategyProfile requires these fields in your repo.
    # We keep permissive defaults for this harness.
    profile = StrategyProfile(
        name="REPLAY_PROFILE",
        description="Alpha hold-period robustness harness profile",
        min_signal_strength=0.0,
        max_trades_per_week=10_000_000,
        allow_trend=True,
        allow_mean_reversion=True,
        risk_bias_multiplier=1.0,
    )

    engine = SignalEngine(profile)

    alpha_pnls: List[float] = []

    start_i = args.ma_window + 1
    end_i = len(prices) - 1 - args.hold  # ensure i+hold exists

    for i in range(start_i, end_i):
        ma = sma(prices, args.ma_window, i)
        if ma is None:
            continue

        sig = engine.generate(
            instrument=args.instrument,
            price_now=prices[i],
            price_prev=prices[i - 1],
            moving_avg=ma,
        )

        if sig.direction == "FLAT":
            continue
        if float(sig.strength) < args.minsig:
            continue

        # Equal-notional N-bar PnL
        delta = prices[i + args.hold] - prices[i]
        pnl = delta if sig.direction == "BUY" else -delta
        alpha_pnls.append(float(pnl))

    stats = summarize(alpha_pnls)

    print("\n=== ALPHA RESULTS ===")
    print(json.dumps(stats, indent=2))

    out_dir = Path("audit_logs/governance_retention_equal")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"alpha_hold{args.hold}_minsig_{args.minsig:.2f}.json"
    out_path.write_text(
        json.dumps(
            {
                "csv": str(csv_path),
                "instrument": args.instrument,
                "minsig": args.minsig,
                "ma_window": args.ma_window,
                "hold": args.hold,
                "alpha": stats,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote: {out_path}\n")


if __name__ == "__main__":
    main()