"""
Replay Signal Threshold Sweep (CSV) - SAFE
-----------------------------------------
Deterministic threshold sweep using the SAME signal style as run_replay_from_csv.py
(Paper-only; no broker, no live execution.)

Key fixes vs earlier versions:
- Robust header normalization (BOM/whitespace/case) to support: ts_utc,o,h,l,c,v
- Removes ExecutionGate call entirely (execution is disabled anyway; sweep is paper-only)

CSV supported:
  • Header OHLCV: ts_utc,o,h,l,c,v
  • Header OHLCV: timestamp,open,high,low,close,volume
  • Header 2-col: timestamp,price (or date/close etc.)
  • No-header OHLCV: timestamp,open,high,low,close,volume
  • No-header 2-col: timestamp,price

Run:
  python -m tools.replay_sig_threshold_sweep sample_spy_1m_long.csv --min 0.10 --max 0.40 --step 0.05
"""

from __future__ import annotations

import sys
import os
import csv
import time
import argparse
from typing import List, Tuple, Dict, Optional

# Ensure project root is in Python path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


# ============================================================
# CSV LOADER (ROBUST)
# ============================================================

def _looks_like_header(first_line: str) -> bool:
    s = first_line.strip()
    if not s:
        return False
    # Your data lines begin with year digits; headers begin with letters like ts_utc
    if s[:1].isdigit():
        return False
    first_token = s.split(",")[0].strip()
    return any(ch.isalpha() or ch == "_" for ch in first_token)


def _norm(s: str) -> str:
    # normalize for BOM, whitespace, case
    return s.replace("\ufeff", "").strip().lower()


def load_prices(path: str) -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        first = f.readline()
        if not first:
            raise ValueError("CSV is empty")
        f.seek(0)

        has_header = _looks_like_header(first)

        if has_header:
            reader = csv.DictReader(f)
            raw_fields = (reader.fieldnames or [])
            norm_to_raw: Dict[str, str] = {_norm(x): x for x in raw_fields}
            fns_norm = list(norm_to_raw.keys())

            # Accept compact OHLCV header scheme too
            ts_candidates = ["timestamp", "ts_utc", "date", "time", "datetime"]
            px_candidates = ["price", "close", "c", "adj_close", "last"]

            ts_norm = next((k for k in ts_candidates if k in fns_norm), None)
            px_norm = next((k for k in px_candidates if k in fns_norm), None)

            if not ts_norm or not px_norm:
                raise ValueError(f"CSV headers not recognized. Found: {raw_fields}")

            ts_field = norm_to_raw[ts_norm]
            px_field = norm_to_raw[px_norm]

            for r in reader:
                ts = str(r[ts_field])
                px = float(r[px_field])
                rows.append((ts, px))

        else:
            raw = csv.reader(f)
            for r in raw:
                if not r:
                    continue
                # No-header OHLCV: ts,open,high,low,close,(vol...)
                if len(r) >= 5:
                    rows.append((str(r[0]), float(r[4])))
                # No-header 2-col: ts,price
                elif len(r) >= 2:
                    rows.append((str(r[0]), float(r[1])))

    if len(rows) < 3:
        raise ValueError("CSV must contain at least 3 rows")

    return rows


# ============================================================
# SIGNAL
# ============================================================

def momentum_signal(prev_px: float, px: float) -> float:
    """
    Placeholder signal in [-1, +1]:
    - Positive when price rising, negative when falling.
    """
    if prev_px <= 0:
        return 0.0
    delta = (px - prev_px) / prev_px
    return max(-1.0, min(1.0, delta * 50.0))


# ============================================================
# SINGLE RUN
# ============================================================

def run_once(csv_path: str, cutoff: float) -> dict:
    instrument = "REPLAY_INSTRUMENT"
    starting_equity = 100_000.0
    sim = PaperSimulator(starting_equity=starting_equity)

    rows = load_prices(csv_path)
    bars_5m = max(1, len(rows) // 5)

    _, prev_px = rows[0]

    for i in range(1, len(rows)):
        ts_str, px = rows[i]
        sig = momentum_signal(prev_px, px)

        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum",
            source="replay",
            signal_type="indicator",
            value=sig,
            confidence=0.65,
            meta={"timestamp": ts_str},
        )
        envelope = b.build()

        arb = SignalArbitrator.arbitrate(envelope)

        regime = RegimeGate.evaluate(
            bars_5m=bars_5m,
            vol_norm_0_1=0.35,
            spread_bps=7.0,
            high_risk_news=False,
            extra={"instrument": instrument, "ts": ts_str},
        )

        # Paper-only trade rule (ExecutionGate intentionally omitted)
        if arb.allowed and regime.decision == "ALLOW":
            if sig > cutoff and i + 1 < len(rows):
                _, next_px = rows[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="LONG",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                    meta={"sig": sig, "cutoff": cutoff, "ts": ts_str},
                )
            elif sig < -cutoff and i + 1 < len(rows):
                _, next_px = rows[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                    meta={"sig": sig, "cutoff": cutoff, "ts": ts_str},
                )

        prev_px = px

    report = metrics_from_simulator(sim)

    return {
        "cutoff": cutoff,
        "trades": report.trades,
        "wins": report.wins,
        "losses": report.losses,
        "win_rate": report.win_rate,
        "expectancy": report.expectancy,
        "max_drawdown_pct": report.max_drawdown_pct,
        "equity_end": sim.state.equity,
    }


# ============================================================
# SWEEP
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--min", dest="min_cut", type=float, default=0.10)
    ap.add_argument("--max", dest="max_cut", type=float, default=0.40)
    ap.add_argument("--step", type=float, default=0.05)
    args = ap.parse_args()

    cut = args.min_cut
    results = []
    while cut <= args.max_cut + 1e-9:
        results.append(run_once(args.csv_path, round(cut, 4)))
        cut += args.step

    print("\n=== REPLAY SIGNAL CUTOFF SWEEP ===")
    print("cut\ttrades\twin%\texp\tmaxDD%\teq_end")

    for r in results:
        win_rate_pct = float(r["win_rate"]) * 100.0 if r["trades"] else 0.0
        print(
            f'{r["cutoff"]:.2f}\t'
            f'{r["trades"]}\t'
            f'{win_rate_pct:.1f}\t'
            f'{float(r["expectancy"]):.4f}\t'
            f'{float(r["max_drawdown_pct"]):.4f}\t'
            f'{float(r["equity_end"]):.2f}'
        )

    print("\nReplay sweep complete (paper-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())