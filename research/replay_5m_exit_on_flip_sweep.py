"""
Replay 5M Exit-on-Flip Sweep (CSV) - SAFE
----------------------------------------
Aggregates 1m -> 5m closes and runs a replay where positions exit when:
  (a) signal flips against the position, OR
  (b) max_hold bars elapsed

Rules:
- One position at a time (no overlap)
- Entry when sig > +cutoff (LONG) or sig < -cutoff (SHORT)
- Exit-on-flip:
    LONG exits if sig < -flip_cutoff
    SHORT exits if sig > +flip_cutoff
- flip_cutoff defaults to (cutoff * flip_factor), with flip_factor default 0.50

Run:
  python -m tools.replay_5m_exit_on_flip_sweep sample_spy_1m_long.csv --max_hold 6 --min 0.02 --max 0.06 --step 0.01

Recommended starting point based on your discovery:
  cutoff ~ 0.04

Paper-only.
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from dataclasses import dataclass
from typing import List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


SIGNAL_SCALE = 200.0


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

    if len(closes) < 25:
        raise ValueError("Not enough data to run replay.")
    return closes


def aggregate_5m(closes_1m: List[float]) -> List[float]:
    closes_5m: List[float] = []
    for i in range(0, len(closes_1m), 5):
        block = closes_1m[i:i + 5]
        if len(block) == 5:
            closes_5m.append(block[-1])
    if len(closes_5m) < 12:
        raise ValueError("Not enough 5m bars after aggregation.")
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
# POSITION STATE
# ============================================================

@dataclass
class OpenPos:
    direction: str          # "LONG" | "SHORT"
    entry_price: float
    entry_index: int
    entry_sig: float


# ============================================================
# RUN ONCE
# ============================================================

def run_once(closes_5m: List[float], cutoff: float, max_hold: int, flip_factor: float) -> dict:
    instrument = "REPLAY_5M_FLIP"
    sim = PaperSimulator(starting_equity=100_000.0)

    flip_cut = max(0.0, min(1.0, cutoff * flip_factor))
    pos: Optional[OpenPos] = None

    prev = closes_5m[0]

    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        sig = momentum_sig(prev, px)

        # Gates (kept for consistency)
        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum_5m",
            source="replay_exit_on_flip",
            signal_type="indicator",
            value=sig,
            confidence=0.80,
            meta={"cutoff": cutoff, "flip_cut": flip_cut},
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

        # If we have an open position, check exit conditions first
        if pos is not None:
            held = i - pos.entry_index
            exit_due_to_hold = held >= max_hold

            exit_due_to_flip = False
            if pos.direction == "LONG":
                # exit if signal flips negative enough
                exit_due_to_flip = sig < -flip_cut
            else:  # SHORT
                exit_due_to_flip = sig > flip_cut

            if exit_due_to_flip or exit_due_to_hold:
                sim.simulate_trade(
                    instrument=instrument,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    exit_price=px,
                    size=100_000,
                    meta={
                        "cutoff": cutoff,
                        "flip_cut": flip_cut,
                        "max_hold": max_hold,
                        "held": held,
                        "exit": "flip" if exit_due_to_flip else "max_hold",
                        "entry_sig": pos.entry_sig,
                        "exit_sig": sig,
                    },
                )
                pos = None  # flat after exit

        # If flat, consider entry
        if pos is None and arb.allowed and regime.decision == "ALLOW":
            if sig > cutoff:
                pos = OpenPos(direction="LONG", entry_price=px, entry_index=i, entry_sig=sig)
            elif sig < -cutoff:
                pos = OpenPos(direction="SHORT", entry_price=px, entry_index=i, entry_sig=sig)

        prev = px

    # If still open at end, close at last price (forced end-of-sample close)
    if pos is not None:
        last_px = closes_5m[-1]
        sim.simulate_trade(
            instrument=instrument,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=last_px,
            size=100_000,
            meta={
                "cutoff": cutoff,
                "flip_cut": flip_cut,
                "max_hold": max_hold,
                "exit": "eos_close",
            },
        )

    report = metrics_from_simulator(sim)
    return {
        "cutoff": cutoff,
        "flip_cut": flip_cut,
        "max_hold": max_hold,
        "trades": report.trades,
        "win_rate": report.win_rate,
        "expectancy": report.expectancy,
        "max_drawdown_pct": report.max_drawdown_pct,
        "equity_end": sim.state.equity,
    }


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--max_hold", type=int, default=6)
    ap.add_argument("--flip_factor", type=float, default=0.50)
    ap.add_argument("--min", dest="min_cut", type=float, default=0.02)
    ap.add_argument("--max", dest="max_cut", type=float, default=0.06)
    ap.add_argument("--step", type=float, default=0.01)
    args = ap.parse_args()

    if args.max_hold < 1:
        raise ValueError("--max_hold must be >= 1")
    if args.flip_factor <= 0:
        raise ValueError("--flip_factor must be > 0")

    closes_1m = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes_1m)

    cut = args.min_cut
    results = []
    while cut <= args.max_cut + 1e-9:
        results.append(run_once(closes_5m, round(cut, 4), args.max_hold, args.flip_factor))
        cut += args.step

    print(f"\n=== 5M EXIT-ON-FLIP SWEEP (max_hold={args.max_hold}, flip_factor={args.flip_factor}) ===")
    print("cut\ttrades\twin%\texp\tmaxDD%\teq_end\tflip_cut")

    for r in results:
        print(
            f'{r["cutoff"]:.2f}\t'
            f'{r["trades"]}\t'
            f'{float(r["win_rate"])*100:.1f}\t'
            f'{float(r["expectancy"]):.4f}\t'
            f'{float(r["max_drawdown_pct"]):.4f}\t'
            f'{float(r["equity_end"]):.2f}\t'
            f'{float(r["flip_cut"]):.3f}'
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())