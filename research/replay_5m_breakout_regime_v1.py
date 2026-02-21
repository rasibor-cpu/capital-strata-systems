"""
5M Breakout + Vol Expansion + Size Compression

Structure:
- Entry: |sig| > cutoff
- Vol expansion required
- hold = 2
- Size compression in weak vol
"""

from __future__ import annotations
import sys, os, csv, argparse, statistics
from typing import List, Optional
from dataclasses import dataclass

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
BASE_SIZE = 100_000


def load_close_series(path: str) -> List[float]:
    closes = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader)
        has_header = not first[0][:1].isdigit()

        if has_header:
            headers = [x.strip().lower() for x in first]
            idx = headers.index("close") if "close" in headers else 4
            for row in reader:
                closes.append(float(row[idx]))
        else:
            closes.append(float(first[4]))
            for row in reader:
                closes.append(float(row[4]))
    return closes


def aggregate_5m(closes_1m: List[float]) -> List[float]:
    return [closes_1m[i+4] for i in range(0, len(closes_1m)-4, 5)]


def momentum_sig(prev, px):
    ret = (px - prev) / prev if prev > 0 else 0.0
    return max(-1, min(1, ret * SIGNAL_SCALE))


@dataclass
class OpenPos:
    direction: str
    entry_price: float
    entry_index: int
    size: float


def run_model(closes_5m, cutoff, hold):

    sim = PaperSimulator(starting_equity=100_000.0)
    pos: Optional[OpenPos] = None
    returns = []
    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        ret = (px - prev) / prev if prev > 0 else 0.0
        returns.append(ret)

        sig = momentum_sig(prev, px)

        if len(returns) >= ROLL_WINDOW:
            avg_abs = statistics.mean([abs(r) for r in returns[-ROLL_WINDOW:]])
            median_abs = statistics.median([abs(r) for r in returns])
        else:
            avg_abs = 0
            median_abs = 0

        vol_expansion = avg_abs > 1.2 * median_abs if median_abs > 0 else False

        # Regime-based size compression
        if avg_abs < 0.8 * median_abs and median_abs > 0:
            size = BASE_SIZE * 0.5
        else:
            size = BASE_SIZE

        # EXIT
        if pos:
            if i - pos.entry_index >= hold:
                sim.simulate_trade(
                    instrument="BREAKOUT_REGIME",
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=px,
                    size=pos.size,
                )
                pos = None

        # ENTRY
        if not pos and vol_expansion:
            if sig > cutoff:
                pos = OpenPos("LONG", px, i, size)
            elif sig < -cutoff:
                pos = OpenPos("SHORT", px, i, size)

        prev = px

    report = metrics_from_simulator(sim)
    return report, sim.state.equity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--cut", type=float, default=0.04)
    ap.add_argument("--hold", type=int, default=2)
    args = ap.parse_args()

    closes = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes)

    report, eq = run_model(closes_5m, args.cut, args.hold)

    print("\n=== BREAKOUT REGIME V1 ===")
    print(f"trades={report.trades}")
    print(f"win%={report.win_rate*100:.1f}")
    print(f"expectancy={report.expectancy:.4f}")
    print(f"maxDD%={report.max_drawdown_pct:.4f}")
    print(f"equity_end={eq:.2f}")


if __name__ == "__main__":
    main()