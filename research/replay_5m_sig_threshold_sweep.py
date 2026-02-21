"""
Replay 5-Minute Signal Threshold Sweep (CSV) - SAFE
---------------------------------------------------
Aggregates 1-minute OHLCV into 5-minute bars,
then runs momentum-based replay sweep.

Run:
  python -m tools.replay_5m_sig_threshold_sweep sample_spy_1m_long.csv --min 0.01 --max 0.08 --step 0.01

Paper-only.
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from typing import List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


# ============================================================
# CSV LOADER (CLOSE ONLY)
# ============================================================

def load_close_series(path: str) -> List[float]:
    closes = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader)
        has_header = not first[0][:1].isdigit()

        def parse_close(row):
            if len(row) >= 5:
                return float(row[4])
            elif len(row) >= 2:
                return float(row[1])
            return None

        if has_header:
            headers = [x.strip().lower() for x in first]
            idx = None
            for i, h in enumerate(headers):
                if h in ["close", "c", "price", "adj_close"]:
                    idx = i
                    break
            if idx is None:
                raise ValueError("Close column not found.")
            for row in reader:
                if row:
                    closes.append(float(row[idx]))
        else:
            c = parse_close(first)
            if c is not None:
                closes.append(c)
            for row in reader:
                c = parse_close(row)
                if c is not None:
                    closes.append(c)

    return closes


# ============================================================
# 5M AGGREGATION
# ============================================================

def aggregate_5m(closes: List[float]) -> List[float]:
    agg = []
    for i in range(0, len(closes), 5):
        block = closes[i:i+5]
        if len(block) == 5:
            agg.append(block[-1])  # use close of 5m bar
    return agg


# ============================================================
# SIGNAL
# ============================================================

def momentum_signal(prev_px: float, px: float, scale: float = 50.0) -> float:
    if prev_px <= 0:
        return 0.0
    delta = (px - prev_px) / prev_px
    return max(-1.0, min(1.0, delta * scale))


# ============================================================
# SINGLE RUN
# ============================================================

def run_once(closes_5m: List[float], cutoff: float) -> dict:
    instrument = "REPLAY_5M"
    sim = PaperSimulator(starting_equity=100_000.0)

    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        sig = momentum_signal(prev, px, scale=200.0)  # stronger scaling for 5m

        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum_5m",
            source="replay_5m",
            signal_type="indicator",
            value=sig,
            confidence=0.75,
            meta={},
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

        if arb.allowed and regime.decision == "ALLOW":
            if sig > cutoff and i + 1 < len(closes_5m):
                next_px = closes_5m[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="LONG",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                )
            elif sig < -cutoff and i + 1 < len(closes_5m):
                next_px = closes_5m[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                )

        prev = px

    report = metrics_from_simulator(sim)

    return {
        "cutoff": cutoff,
        "trades": report.trades,
        "win_rate": report.win_rate,
        "expectancy": report.expectancy,
        "max_drawdown_pct": report.max_drawdown_pct,
        "equity_end": sim.state.equity,
    }


# ============================================================
# SWEEP
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--min", type=float, default=0.01)
    ap.add_argument("--max", type=float, default=0.08)
    ap.add_argument("--step", type=float, default=0.01)
    args = ap.parse_args()

    closes = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes)

    cut = args.min
    results = []

    while cut <= args.max + 1e-9:
        results.append(run_once(closes_5m, round(cut, 4)))
        cut += args.step

    print("\n=== 5M REPLAY SIGNAL CUTOFF SWEEP ===")
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


if __name__ == "__main__":
    main()