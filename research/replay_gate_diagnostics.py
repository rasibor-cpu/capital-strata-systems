"""
Replay Gate Diagnostics (CSV) - SAFE
------------------------------------
Diagnoses why replay runs produce zero trades.

Counts, for a given cutoff:
- bars processed
- arb.allowed count
- regime ALLOW count
- |sig| > cutoff count
- all conditions satisfied count (trade opportunities)

Run:
  python -m tools.replay_gate_diagnostics sample_spy_1m_long.csv --cutoff 0.10

Optional:
  --print-reasons  (prints top block reasons samples)
"""

from __future__ import annotations

import sys
import os
import csv
import argparse
from collections import Counter
from typing import List, Tuple, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate


def _looks_like_header(first_line: str) -> bool:
    s = first_line.strip()
    if not s:
        return False
    if s[:1].isdigit():
        return False
    first_token = s.split(",")[0].strip()
    return any(ch.isalpha() or ch == "_" for ch in first_token)


def _norm(s: str) -> str:
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

            ts_candidates = ["timestamp", "ts_utc", "date", "time", "datetime"]
            px_candidates = ["price", "close", "c", "adj_close", "last"]

            ts_norm = next((k for k in ts_candidates if k in fns_norm), None)
            px_norm = next((k for k in px_candidates if k in fns_norm), None)

            if not ts_norm or not px_norm:
                raise ValueError(f"CSV headers not recognized. Found: {raw_fields}")

            ts_field = norm_to_raw[ts_norm]
            px_field = norm_to_raw[px_norm]

            for r in reader:
                rows.append((str(r[ts_field]), float(r[px_field])))

        else:
            raw = csv.reader(f)
            for r in raw:
                if not r:
                    continue
                if len(r) >= 5:
                    rows.append((str(r[0]), float(r[4])))  # close
                elif len(r) >= 2:
                    rows.append((str(r[0]), float(r[1])))

    if len(rows) < 3:
        raise ValueError("CSV must contain at least 3 rows")
    return rows


def momentum_signal(prev_px: float, px: float) -> float:
    if prev_px <= 0:
        return 0.0
    delta = (px - prev_px) / prev_px
    return max(-1.0, min(1.0, delta * 50.0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=str)
    ap.add_argument("--cutoff", type=float, default=0.10)
    ap.add_argument("--print-reasons", action="store_true")
    args = ap.parse_args()

    rows = load_prices(args.csv_path)
    instrument = "REPLAY_INSTRUMENT"
    bars_5m = max(1, len(rows) // 5)

    total_bars = 0
    arb_allow = 0
    regime_allow = 0
    sig_pass = 0
    all_pass = 0

    arb_block_reasons = Counter()
    regime_reasons = Counter()

    _, prev_px = rows[0]
    for i in range(1, len(rows)):
        ts_str, px = rows[i]
        sig = momentum_signal(prev_px, px)
        total_bars += 1

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
        if arb.allowed:
            arb_allow += 1
        else:
            arb_block_reasons[str(getattr(arb, "reason", "BLOCK"))] += 1

        regime = RegimeGate.evaluate(
            bars_5m=bars_5m,
            vol_norm_0_1=0.35,
            spread_bps=7.0,
            high_risk_news=False,
            extra={"instrument": instrument, "ts": ts_str},
        )
        if getattr(regime, "decision", "") == "ALLOW":
            regime_allow += 1
        else:
            regime_reasons[str(getattr(regime, "reason", getattr(regime, "decision", "BLOCK")))] += 1

        if abs(sig) > args.cutoff:
            sig_pass += 1

        if arb.allowed and getattr(regime, "decision", "") == "ALLOW" and abs(sig) > args.cutoff:
            all_pass += 1

        prev_px = px

    print("\n=== REPLAY GATE DIAGNOSTICS ===")
    print(f"rows={len(rows)}  bars_processed={total_bars}  cutoff={args.cutoff:.2f}")
    print(f"arb_allowed={arb_allow}  regime_allow={regime_allow}  |sig|>cutoff={sig_pass}")
    print(f"ALL_CONDITIONS_PASS (trade opportunities) = {all_pass}")

    if args.print_reasons:
        print("\nTop Arb block reasons:")
        for k, v in arb_block_reasons.most_common(8):
            print(f"  {v}  {k}")

        print("\nTop Regime block reasons:")
        for k, v in regime_reasons.most_common(8):
            print(f"  {v}  {k}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())