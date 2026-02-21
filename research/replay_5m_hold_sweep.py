"""
Replay 5M Multi-Bar Hold Sweep (CSV) - SAFE
-------------------------------------------
Aggregates 1m OHLCV into 5m closes, then note:
- Entry when |sig| exceeds cutoff (and gates ALLOW)
- Exit after HOLD_BARS bars (fixed hold)

Run examples:
  python -m tools.replay_5m_hold_sweep sample_spy_1m_long.csv --hold 2 --min 0.01 --max 0.08 --step 0.01
  python -m tools.replay_5m_hold_sweep sample_spy_1m_long.csv --hold 3 --min 0.01 --max 0.08 --step 0.01

Paper-only.
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


# ============================================================
# LOAD CLOSE SERIES
# ============================================================

def load_close_series(path: str) -> List[float]:
    closes: List[float] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader)
        has_header = not first[0][:1].isdigit()

        def parse_close(row):
            if len(row) >= 5:
                return float(row[4])  # close (OHLCV)
            if len(row) >= 2:
                return float(row[1])  # price (2-col)
            return None

        if has_header:
            headers = [x.strip().lower() for x in first]
            idx = None
            for i, h in enumerate(headers):
                if h in ["close", "c", "price", "adj_close", "last"]:
                    idx = i
                    break
            if idx is None:
                raise ValueError("Close column not found in header.")
            for row in reader:
                if row and len(row) > idx:
                    closes.append(float(row[idx]))
        else:
            c0 = parse_close(first)
            if c0 is not None:
                closes.append(c0)
            for row in reader:
                c = parse_close(row)
                if c is not None:
                    closes.append(c)

    if len(closes) < 10:
        raise ValueError("Not enough data to run replay.")
    return closes


def aggregate_5m(closes_1m: List[float]) -> List[float]:
    closes_5m: List[float] = []
    for i in range(0, len(closes_1m), 5):
        block = closes_1m[i:i + 5]
        if len(block) == 5:
            closes_5m.append(block[-1])
    if len(closes_5m) < 10:
        raise ValueError("Not enough 5m bars after aggregation.")
    return closes_5m


# ============================================================
# SIGNAL
# ============================================================

def momentum_signal(prev_px: float, px: float, scale: float) -> float:
    if prev_px <= 0:
        return 0.0
    delta = (px - prev_px) / prev_px
    x = delta * scale
    return max(-1.0, min(1.0, x))


# ============================================================
# RUN ONCE (fixed hold)
# ============================================================

def run_once(closes_5m: List[float], cutoff: float, hold_bars: int, signal_scale: float) -> dict:
    instrument = f"REPLAY_5M_H{hold_bars}"
    sim = PaperSimulator(starting_equity=100_000.0)

    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        sig = momentum_signal(prev, px, scale=signal_scale)

        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum_5m",
            source="replay_5m_hold",
            signal_type="indicator",
            value=sig,
            confidence=0.80,
            meta={"hold": hold_bars},
        )
        envelope = b.build()

        arb = SignalArbitrator.arbitrate(envelope)
        regime = RegimeGate.evaluate(
            bars_5m=len(closes_5m),
            vol_norm_0_1=0.35,
            spread_bps=5.0,
            high_risk_news=False,
            extra={"instrument": instrument},
        )

        # Entry rule + fixed-hold exit
        exit_i = i + hold_bars
        if arb.allowed and regime.decision == "ALLOW" and exit_i < len(closes_5m):
            if sig > cutoff:
                entry_px = px
                exit_px = closes_5m[exit_i]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="LONG",
                    entry_price=entry_px,
                    exit_price=exit_px,
                    size=100_000,
                    meta={"cutoff": cutoff, "sig": sig, "hold": hold_bars},
                )
            elif sig < -cutoff:
                entry_px = px
                exit_px = closes_5m[exit_i]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=entry_px,
                    exit_price=exit_px,
                    size=100_000,
                    meta={"cutoff": cutoff, "sig": sig, "hold": hold_bars},
                )

        prev = px

    report = metrics_from_simulator(sim)

    return {
        "cutoff": cutoff,
        "hold": hold_bars,
        "trades": report.trades,
        "win_rate": report.win_rate,
        "expectancy": report.expectancy,
        "max_drawdown_pct": report.max_drawdown_pct,
        "equity_end": sim.state.equity,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--hold", type=int, default=2, help="Hold bars after entry (2 or 3 recommended).")
    ap.add_argument("--min", dest="min_cut", type=float, default=0.01)
    ap.add_argument("--max", dest="max_cut", type=float, default=0.08)
    ap.add_argument("--step", type=float, default=0.01)
    ap.add_argument("--scale", type=float, default=200.0, help="Signal scaling factor for 5m returns.")
    args = ap.parse_args()

    if args.hold < 1:
        raise ValueError("--hold must be >= 1")

    closes_1m = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes_1m)

    cut = args.min_cut
    results = []
    while cut <= args.max_cut + 1e-9:
        results.append(run_once(closes_5m, round(cut, 4), args.hold, args.scale))
        cut += args.step

    print(f"\n=== 5M HOLD SWEEP (hold={args.hold}, scale={args.scale}) ===")
    print("cut\ttrades\twin%\texp\tmaxDD%\teq_end")

    for r in results:
        print(
            f'{r["cutoff"]:.2f}\t'
            f'{r["trades"]}\t'
            f'{float(r["win_rate"])*100:.1f}\t'
            f'{float(r["expectancy"]):.4f}\t'
            f'{float(r["max_drawdown_pct"]):.4f}\t'
            f'{float(r["equity_end"]):.2f}'
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())