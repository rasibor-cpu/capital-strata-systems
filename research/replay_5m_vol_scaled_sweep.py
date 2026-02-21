"""
Replay 5M Volatility-Scaled Threshold Sweep (CSV) - SAFE
--------------------------------------------------------
Institutional corrected version:
Volatility scaled in SAME space as signal.

signal = return * SIGNAL_SCALE
dynamic_cutoff = max(base_cutoff, k * rolling_vol * SIGNAL_SCALE)

Run:
  python -m tools.replay_5m_vol_scaled_sweep sample_spy_1m_long.csv --base 0.02 --k 4.0
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from typing import List
import statistics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


SIGNAL_SCALE = 200.0
ROLLING_WINDOW = 10


# ============================================================
# LOAD CLOSE SERIES
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
            agg.append(block[-1])
    return agg


# ============================================================
# VOL-SCALED RUN (CORRECTED)
# ============================================================

def run_vol_scaled(closes_5m: List[float], base_cutoff: float, k: float) -> dict:
    instrument = "REPLAY_5M_VOL"
    sim = PaperSimulator(starting_equity=100_000.0)

    returns = []
    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        ret = (px - prev) / prev if prev > 0 else 0.0
        returns.append(ret)

        if len(returns) < ROLLING_WINDOW:
            prev = px
            continue

        rolling_vol = statistics.pstdev(returns[-ROLLING_WINDOW:])
        sig = ret * SIGNAL_SCALE

        dynamic_cutoff = max(base_cutoff, k * rolling_vol * SIGNAL_SCALE)

        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum_5m",
            source="replay_vol_scaled",
            signal_type="indicator",
            value=sig,
            confidence=0.8,
            meta={"rolling_vol": rolling_vol},
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
            if sig > dynamic_cutoff and i + 1 < len(closes_5m):
                sim.simulate_trade(
                    instrument=instrument,
                    direction="LONG",
                    entry_price=px,
                    exit_price=closes_5m[i + 1],
                    size=100_000,
                )
            elif sig < -dynamic_cutoff and i + 1 < len(closes_5m):
                sim.simulate_trade(
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=px,
                    exit_price=closes_5m[i + 1],
                    size=100_000,
                )

        prev = px

    report = metrics_from_simulator(sim)

    return {
        "trades": report.trades,
        "win_rate": report.win_rate,
        "expectancy": report.expectancy,
        "max_drawdown_pct": report.max_drawdown_pct,
        "equity_end": sim.state.equity,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--base", type=float, default=0.02)
    ap.add_argument("--k", type=float, default=4.0)
    args = ap.parse_args()

    closes = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes)

    result = run_vol_scaled(closes_5m, args.base, args.k)

    print("\n=== 5M VOL-SCALED RESULT (CORRECTED) ===")
    print(f"base_cutoff={args.base}  k={args.k}")
    print(f"trades={result['trades']}")
    print(f"win%={result['win_rate']*100:.1f}")
    print(f"expectancy={result['expectancy']:.4f}")
    print(f"maxDD%={result['max_drawdown_pct']:.4f}")
    print(f"equity_end={result['equity_end']:.2f}")


if __name__ == "__main__":
    main()