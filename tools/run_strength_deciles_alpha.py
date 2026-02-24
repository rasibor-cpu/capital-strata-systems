"""
tools/run_strength_deciles_alpha.py

CSS – Strength Deciles (Alpha-only) Diagnostic
---------------------------------------------
Upgraded: MA Slope Confirmation Direction Filter

Goal:
- Test whether adding MA slope confirmation restores edge / fixes inverted deciles.

Direction rule (slope-filtered):
- BUY  if price_now > MA_now and (MA_now - MA_prev) > 0
- SELL if price_now < MA_now and (MA_now - MA_prev) < 0
- else FLAT

Ranking:
- raw  = rank by SignalEngine.strength
- das  = rank by direction-adjusted displacement score

Outputs:
- Prints decile expectancy table
- Prints monotonicity diagnostic
- Writes JSON to audit_logs/strength_deciles_alpha/
"""

from __future__ import annotations

import sys
from pathlib import Path
import argparse
import csv
import json
from statistics import mean
from typing import List, Optional, Dict, Any, Tuple
import math

# Ensure repo root is visible
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


def summarize(pnls: List[float]) -> Dict[str, Any]:
    if not pnls:
        return {"trades": 0, "expectancy": 0.0, "winrate": 0.0, "total_pnl": 0.0}
    wins = [p for p in pnls if p > 0]
    return {
        "trades": len(pnls),
        "expectancy": float(mean(pnls)),
        "winrate": float(len(wins) / len(pnls)),
        "total_pnl": float(sum(pnls)),
    }


def build_profile() -> StrategyProfile:
    return StrategyProfile(
        name="DECILES_PROFILE",
        description="Strength-decile alpha diagnostic profile",
        min_signal_strength=0.0,
        max_trades_per_week=10_000_000,
        allow_trend=True,
        allow_mean_reversion=True,
        risk_bias_multiplier=1.0,
    )


def equal_population_deciles(trades: List[Tuple[float, float]]) -> List[List[Tuple[float, float]]]:
    trades_sorted = sorted(trades, key=lambda x: x[0])
    n = len(trades_sorted)
    if n == 0:
        return [[] for _ in range(10)]
    buckets: List[List[Tuple[float, float]]] = []
    for d in range(10):
        lo = int(d * n / 10)
        hi = int((d + 1) * n / 10)
        buckets.append(trades_sorted[lo:hi])
    return buckets


def monotonicity_score(expectancies: List[float]) -> Dict[str, Any]:
    increases = 0
    for i in range(9):
        if expectancies[i + 1] >= expectancies[i]:
            increases += 1
    ratio = increases / 9.0
    return {
        "ok": True,
        "non_decreasing_steps": increases,
        "steps": 9,
        "monotonicity_ratio": float(ratio),
        "d10_gt_d1": bool(expectancies[9] > expectancies[0]),
        "d10": float(expectancies[9]),
        "d1": float(expectancies[0]),
    }


def sigmoid01(x: float, k: float = 1.0) -> float:
    x = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-k * x))


def compute_das(price_now: float, moving_avg: float, atr_proxy: float, direction: str) -> float:
    atr = max(float(atr_proxy), 1e-9)
    signed_z = (price_now - moving_avg) / atr
    if direction == "SELL":
        signed_z = -signed_z

    score = sigmoid01((abs(signed_z) - 0.6) * 1.8, k=1.0)
    if signed_z < 0:
        score *= 0.10
    return max(0.0, min(1.0, float(score)))


def slope_filtered_direction(price_now: float, ma_now: float, ma_prev: float) -> str:
    slope = ma_now - ma_prev
    if price_now > ma_now and slope > 0:
        return "BUY"
    if price_now < ma_now and slope < 0:
        return "SELL"
    return "FLAT"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", default="GBP_USD")
    ap.add_argument("--ma_window", type=int, default=20)
    ap.add_argument("--hold", type=int, default=1)
    ap.add_argument("--rank", choices=["raw", "das"], default="raw")
    ap.add_argument("--minsig_floor", type=float, default=0.0)
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    prices = load_prices(csv_path)
    print(f"\nCSV: {csv_path}")
    print(f"Prices loaded: {len(prices)}")
    print(f"Instrument: {args.instrument}")
    print(f"MA window: {args.ma_window}")
    print(f"Hold (bars): {args.hold}")
    print(f"Rank mode: {args.rank}")
    print(f"minsig_floor: {args.minsig_floor}")
    print("Direction filter: MA slope confirmation = ON")

    if args.hold < 1:
        raise ValueError("--hold must be >= 1")

    # Need MA_prev too => start one bar later
    if len(prices) < args.ma_window + args.hold + 6:
        raise ValueError("Not enough price rows for MA window + hold + slope.")

    profile = build_profile()
    engine = SignalEngine(profile)

    trades: List[Tuple[float, float]] = []

    start_i = args.ma_window + 2
    end_i = len(prices) - 1 - args.hold

    for i in range(start_i, end_i):
        ma_now = sma(prices, args.ma_window, i)
        ma_prev = sma(prices, args.ma_window, i - 1)
        if ma_now is None or ma_prev is None:
            continue

        # Direction is slope-filtered (external)
        dir2 = slope_filtered_direction(prices[i], ma_now, ma_prev)
        if dir2 == "FLAT":
            continue

        # Still call SignalEngine to get its raw strength value
        sig = engine.generate(
            instrument=args.instrument,
            price_now=prices[i],
            price_prev=prices[i - 1],
            moving_avg=ma_now,
        )

        strength_raw = float(sig.strength)
        if strength_raw < args.minsig_floor:
            continue

        delta = prices[i + args.hold] - prices[i]
        pnl = delta if dir2 == "BUY" else -delta

        atr_proxy = abs(prices[i] - prices[i - 1])

        if args.rank == "raw":
            rank_strength = strength_raw
        else:
            rank_strength = compute_das(prices[i], ma_now, atr_proxy, dir2)

        trades.append((float(rank_strength), float(pnl)))

    print(f"\nSignals captured (slope-filtered): {len(trades)}")

    buckets = equal_population_deciles(trades)

    decile_stats: List[Dict[str, Any]] = []
    expectancies: List[float] = []

    for idx, b in enumerate(buckets, start=1):
        pnls = [p for _, p in b]
        st = summarize(pnls)
        if b:
            st["rank_min"] = float(min(s for s, _ in b))
            st["rank_max"] = float(max(s for s, _ in b))
        else:
            st["rank_min"] = None
            st["rank_max"] = None
        st["decile"] = idx
        decile_stats.append(st)
        expectancies.append(float(st["expectancy"]))

    mono = monotonicity_score(expectancies)

    print("\n=== DECILE EXPECTANCIES (D1=weakest .. D10=strongest) ===")
    for st in decile_stats:
        print(
            f"D{st['decile']}: trades={st['trades']}, exp={st['expectancy']:.8e}, "
            f"win={st['winrate']:.4f}, rank=[{st['rank_min']},{st['rank_max']}]"
        )

    print("\n=== MONOTONICITY DIAGNOSTIC ===")
    print(json.dumps(mono, indent=2))

    out_dir = Path("audit_logs/strength_deciles_alpha")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"deciles_slope_{args.rank}_hold{args.hold}_ma{args.ma_window}_floor{args.minsig_floor:.2f}.json"
    out_path.write_text(
        json.dumps(
            {
                "csv": str(csv_path),
                "instrument": args.instrument,
                "ma_window": args.ma_window,
                "hold": args.hold,
                "rank": args.rank,
                "minsig_floor": args.minsig_floor,
                "signals": len(trades),
                "direction_filter": "ma_slope_confirmation",
                "deciles": decile_stats,
                "monotonicity": mono,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote: {out_path}\n")


if __name__ == "__main__":
    main()