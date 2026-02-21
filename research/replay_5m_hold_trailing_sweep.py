"""
Replay 5M Breakout + Vol-Scaled Trailing Stop (Improved)

Changes:
- Trailing uses mean absolute return (not stdev)
- Activation requires unrealized > 1.5 × trail_distance
- Preserves breakout structure
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from typing import List, Optional, Tuple
from dataclasses import dataclass
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
ROLL_WINDOW = 5
ACTIVATION_MULTIPLE = 1.5


# ============================================================
# LOAD + AGGREGATE
# ============================================================

def load_close_series(path: str) -> List[float]:
    closes: List[float] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader)
        has_header = not first[0][:1].isdigit()

        def parse_close(row):
            if len(row) >= 5:
                return float(row[4])
            if len(row) >= 2:
                return float(row[1])
            return None

        if has_header:
            headers = [x.strip().lower() for x in first]
            idx = None
            for i, h in enumerate(headers):
                if h in ["close", "c", "price", "adj_close", "last"]:
                    idx = i
                    break
            if idx is None:
                raise ValueError("Close column not found.")
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

    return closes


def aggregate_5m(closes_1m: List[float]) -> List[float]:
    closes_5m: List[float] = []
    for i in range(0, len(closes_1m), 5):
        block = closes_1m[i:i + 5]
        if len(block) == 5:
            closes_5m.append(block[-1])
    return closes_5m


# ============================================================
# SIGNAL
# ============================================================

def momentum_sig(prev_px: float, px: float) -> float:
    if prev_px <= 0:
        return 0.0
    ret = (px - prev_px) / prev_px
    x = ret * SIGNAL_SCALE
    return max(-1.0, min(1.0, x))


# ============================================================
# POSITION
# ============================================================

@dataclass
class OpenPos:
    direction: str
    entry_price: float
    entry_index: int
    peak_price: float


# ============================================================
# MODEL
# ============================================================

def run_model(closes_5m: List[float], cutoff: float, hold_bars: int, trail_k: float):

    instrument = "REPLAY_5M_TRAIL_V2"
    sim = PaperSimulator(starting_equity=100_000.0)

    pos: Optional[OpenPos] = None
    returns: List[float] = []

    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        ret = (px - prev) / prev if prev > 0 else 0.0
        returns.append(ret)

        sig = momentum_sig(prev, px)

        if len(returns) >= ROLL_WINDOW:
            avg_abs_ret = statistics.mean([abs(r) for r in returns[-ROLL_WINDOW:]])
        else:
            avg_abs_ret = 0.0

        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum_5m",
            source="replay_trailing_v2",
            signal_type="indicator",
            value=sig,
            confidence=0.8,
            meta={"avg_abs_ret": avg_abs_ret},
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

        # ---------------- EXIT ----------------
        if pos is not None:
            held = i - pos.entry_index
            exit_hold = held >= hold_bars

            trail_distance = trail_k * avg_abs_ret * pos.entry_price

            if pos.direction == "LONG":
                pos.peak_price = max(pos.peak_price, px)
                unrealized = px - pos.entry_price
                activation = unrealized > ACTIVATION_MULTIPLE * trail_distance
                stop_price = pos.peak_price - trail_distance
                exit_trail = activation and (px < stop_price)
            else:
                pos.peak_price = min(pos.peak_price, px)
                unrealized = pos.entry_price - px
                activation = unrealized > ACTIVATION_MULTIPLE * trail_distance
                stop_price = pos.peak_price + trail_distance
                exit_trail = activation and (px > stop_price)

            if exit_trail or exit_hold:
                sim.simulate_trade(
                    instrument=instrument,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=px,
                    size=100_000,
                )
                pos = None

        # ---------------- ENTRY ----------------
        if pos is None and arb.allowed and regime.decision == "ALLOW":
            if sig > cutoff:
                pos = OpenPos("LONG", px, i, px)
            elif sig < -cutoff:
                pos = OpenPos("SHORT", px, i, px)

        prev = px

    report = metrics_from_simulator(sim)
    return report, sim.state.equity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--cut", type=float, default=0.04)
    ap.add_argument("--hold", type=int, default=2)
    ap.add_argument("--trail_k", type=float, default=2.0)
    args = ap.parse_args()

    closes_1m = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes_1m)

    report, equity_end = run_model(closes_5m, args.cut, args.hold, args.trail_k)

    print("\n=== 5M BREAKOUT + TRAILING RESULT (V2) ===")
    print(f"cutoff={args.cut}")
    print(f"hold={args.hold}")
    print(f"trail_k={args.trail_k}")
    print(f"trades={report.trades}")
    print(f"win%={report.win_rate*100:.1f}")
    print(f"expectancy={report.expectancy:.4f}")
    print(f"maxDD%={report.max_drawdown_pct:.4f}")
    print(f"equity_end={equity_end:.2f}")


if __name__ == "__main__":
    main()