"""
tools/run_replay_csv_threshold_sweep.py

CSV Replay Runner (SAFE) + Equal-Population Strength Deciles
-----------------------------------------------------------
Purpose:
- Read CSV with at least: timestamp,price  (timestamp optional)
- Generate signals from SignalEngine (alpha-layer)
- Apply minsig threshold gating
- Compute simple 1-bar PnL (directional) for expectancy testing
- Produce equal-population strength decile stats
- Write JSON summary to: audit_logs/threshold_sweep/minsig_<X>.json

IMPORTANT:
- This is ALPHA-LAYER expectancy (SignalEngine only).
- It is intentionally independent of ExecutionGate/RiskGovernor to avoid
  mixing signal ranking with governance throttles when testing monotonicity.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean
from typing import List, Tuple, Dict, Any
from collections import deque


from engine.strategy.signal_engine import SignalEngine

# Behaviour -> StrategyProfile mapping (authoritative in your repo)
from engine.strategy.behaviour_mapper import get_profile_for_behaviour


MA_WINDOW = 20
DEFAULT_PIP_SCALE = 10000.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def compute_equal_population_deciles(strength_pnl: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
    """
    Equal-population deciles:
      - Sort by strength
      - Split into 10 buckets with ~equal counts
    """
    if not strength_pnl:
        return []

    strength_pnl = sorted(strength_pnl, key=lambda t: t[0])
    n = len(strength_pnl)
    bucket = max(1, n // 10)

    out: List[Dict[str, Any]] = []

    for i in range(10):
        start = i * bucket
        end = (i + 1) * bucket if i < 9 else n
        seg = strength_pnl[start:end]
        if not seg:
            continue

        strengths = [s for s, _ in seg]
        pnls = [p for _, p in seg]

        trades = len(seg)
        wins = sum(1 for p in pnls if p > 0)
        losses = trades - wins

        out.append({
            "decile": i + 1,
            "strength_min": round(min(strengths), 6),
            "strength_max": round(max(strengths), 6),
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades, 4) if trades else 0.0,
            "avg_pnl_per_trade": round(mean(pnls), 8) if trades else 0.0,
            "total_pnl": round(sum(pnls), 8),
        })

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV path containing at least a 'price' column")
    ap.add_argument("--instrument", default="USD_GBP", help="Instrument label used in logs")
    ap.add_argument("--behaviour", default="C", help="Behaviour code: A/B/C/D/E (maps to StrategyProfile)")
    ap.add_argument("--minsig", type=float, required=True, help="Minimum signal strength threshold (0..1)")
    ap.add_argument("--pip_scale", type=float, default=DEFAULT_PIP_SCALE, help="Scale for PnL units (FX pips etc.)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    # Resolve profile correctly (this is your authoritative wiring)
    profile = get_profile_for_behaviour(args.behaviour)

    engine = SignalEngine(profile)

    price_window = deque(maxlen=MA_WINDOW)
    prev_price = None

    # Diagnostics
    total_signals = 0
    regime_flat_blocks = 0  # not used here, kept for compatibility shape
    threshold_blocks = 0
    gate_blocks = 0         # not used here, kept for compatibility shape

    trades = 0
    starting_equity = 1000.0
    equity = starting_equity

    # For deciles: (strength, realized_pnl)
    strength_pnl_records: List[Tuple[float, float]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "price" not in reader.fieldnames:
            raise SystemExit(f"CSV must include 'price' column. Found: {reader.fieldnames}")

        for row in reader:
            try:
                price = float(row["price"])
            except Exception:
                continue

            price_window.append(price)

            if prev_price is None:
                prev_price = price
                continue

            # Need MA window before generating signals
            if len(price_window) < 2:
                prev_price = price
                continue

            moving_avg = sum(price_window) / float(len(price_window))

            signal = engine.generate(
                instrument=str(args.instrument),
                price_now=float(price),
                price_prev=float(prev_price),
                moving_avg=float(moving_avg),
            )

            total_signals += 1

            # Gate by minsig (alpha-layer threshold only)
            if signal.direction == "FLAT" or signal.strength < float(args.minsig):
                threshold_blocks += 1
                prev_price = price
                continue

            # Simple 1-bar realized PnL for expectancy ranking test
            direction_sign = 1.0 if signal.direction == "BUY" else -1.0
            delta = float(price) - float(prev_price)
            realized_pnl = delta * direction_sign * float(args.pip_scale)

            equity += realized_pnl
            trades += 1
            strength_pnl_records.append((float(signal.strength), float(realized_pnl)))

            prev_price = price

    net_pnl = equity - starting_equity

    deciles = compute_equal_population_deciles(strength_pnl_records)

    summary: Dict[str, Any] = {
        "bars_ma_window": MA_WINDOW,
        "pip_scale": float(args.pip_scale),
        "min_signal_strength": float(args.minsig),
        "behaviour": str(args.behaviour),
        "profile_name": getattr(profile, "name", "UNKNOWN"),
        "total_signals": int(total_signals),
        "regime_flat_blocks": int(regime_flat_blocks),
        "threshold_blocks": int(threshold_blocks),
        "gate_blocks": int(gate_blocks),
        "trades": int(trades),
        "starting_equity": float(starting_equity),
        "ending_equity": float(equity),
        "net_pnl": float(net_pnl),
        "bars": int(total_signals + 1),  # approx bars processed (signals start after first prev)
        "instrument": str(args.instrument),
        "decile_expectancy": deciles,
        "run_utc": datetime.now(timezone.utc).isoformat(),
    }

    out_dir = Path("audit_logs") / "threshold_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_minsig = str(args.minsig).replace(".", "_")
    out_path = out_dir / f"minsig_{safe_minsig}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== CSS DECILE EXPECTANCY (Equal-Population) ===")
    for d in deciles:
        print(d)

    print("\n=== CSS CSV REPLAY SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote: {out_path}\n")


if __name__ == "__main__":
    main()