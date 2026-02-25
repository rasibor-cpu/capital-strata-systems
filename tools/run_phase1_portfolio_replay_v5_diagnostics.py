"""
Phase 1 – Portfolio Replay V5 Diagnostics (Fail-Open Debug Visibility)
Capital Strata Systems

Purpose:
- Collect a small number of BLOCK samples
- For each BLOCK, print the FULL decision payload (including gate exception string)
- Stop early once enough samples are collected

Usage:
  python -u tools/run_phase1_portfolio_replay_v5_diagnostics.py

Optional env overrides:
  set CSS_BEHAVIOUR=C
  set CSS_MIN_SIGNAL_STRENGTH=0.72
  set CSS_BLOCK_SAMPLES=20
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from collections import deque
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


STARTING_EQUITY = float(os.getenv("CSS_STARTING_EQUITY", "100000"))
BEHAVIOUR = os.getenv("CSS_BEHAVIOUR", "C").strip().upper()
MA_WINDOW = int(os.getenv("CSS_MA_WINDOW", "20"))
STOP_DISTANCE_PCT = float(os.getenv("CSS_STOP_DISTANCE_PCT", "0.01"))
REGIME_PERSISTENCE = float(os.getenv("CSS_GATE_REGIME_PERSISTENCE", "0.95"))
MIN_SIGNAL_STRENGTH = float(os.getenv("CSS_MIN_SIGNAL_STRENGTH", "0.72"))
BLOCK_SAMPLES = int(os.getenv("CSS_BLOCK_SAMPLES", "20"))

DATA_DIR = REPO_ROOT / "data" / "history"
PRICE_COLS = ["close", "price", "Close", "Price", "c"]


def detect_price_col(fields: List[str]) -> str:
    for c in PRICE_COLS:
        if c in fields:
            return c
    return fields[-1]


def load_one_year_m5() -> Dict[str, Dict[str, float]]:
    """
    Returns:
      instrument -> { timestamp_str -> price }
    """
    out: Dict[str, Dict[str, float]] = {}
    for file in sorted(DATA_DIR.glob("*_M5_1year.csv")):
        inst = file.stem.replace("_M5_1year", "").replace("_", "")
        mp: Dict[str, float] = {}
        with open(file, "r", newline="") as f:
            reader = csv.DictReader(f)
            price_col = detect_price_col(reader.fieldnames or ["price"])
            for row in reader:
                ts = row.get("timestamp")
                if not ts:
                    continue
                mp[ts] = float(row[price_col])
        out[inst] = mp
    return out


def is_allow(decision: Any) -> bool:
    if not isinstance(decision, dict):
        return False
    inner = decision.get("decision")
    if isinstance(inner, dict) and str(inner.get("final", "")).upper() == "ALLOW":
        return True
    if str(decision.get("final", "")).upper() == "ALLOW":
        return True
    return False


def main() -> None:
    print("\n==== PHASE 1 PORTFOLIO REPLAY V5 DIAGNOSTIC ====\n")
    print(f"BEHAVIOUR={BEHAVIOUR} | MIN_SIGNAL_STRENGTH={MIN_SIGNAL_STRENGTH} | BLOCK_SAMPLES={BLOCK_SAMPLES}\n")

    data = load_one_year_m5()
    instruments = sorted(data.keys())
    if not instruments:
        print("No *_M5_1year.csv files found under data/history.")
        return

    # Build unified timestamp set
    all_ts = set()
    for mp in data.values():
        all_ts.update(mp.keys())
    sorted_ts = sorted(all_ts)

    profile = get_profile_for_behaviour(BEHAVIOUR)
    engines = {inst: SignalEngine(profile) for inst in instruments}
    gate = ExecutionGate()

    price_windows = {inst: deque(maxlen=MA_WINDOW) for inst in instruments}
    prev_prices: Dict[str, float] = {}
    equity = float(STARTING_EQUITY)
    equity_peak = float(STARTING_EQUITY)

    blocks_collected = 0
    signals_evaluated = 0
    approved = 0

    for ts in sorted_ts:
        # scan instruments at this timestamp
        for inst in instruments:
            mp = data[inst]
            if ts not in mp:
                continue

            price = float(mp[ts])
            price_windows[inst].append(price)

            if inst not in prev_prices:
                prev_prices[inst] = price
                continue

            if len(price_windows[inst]) < MA_WINDOW:
                prev_prices[inst] = price
                continue

            moving_avg = sum(price_windows[inst]) / len(price_windows[inst])

            sig = engines[inst].generate(
                instrument=inst,
                price_now=price,
                price_prev=prev_prices[inst],
                moving_avg=moving_avg,
            )

            signals_evaluated += 1

            if sig.direction == "FLAT":
                prev_prices[inst] = price
                continue

            if float(sig.strength) < float(MIN_SIGNAL_STRENGTH):
                prev_prices[inst] = price
                continue

            equity_peak = max(equity_peak, equity)

            decision = gate.evaluate_trade(
                instrument=inst,
                side=sig.direction,
                notional=equity * 0.10,
                stop_distance_pct=STOP_DISTANCE_PCT,
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=REGIME_PERSISTENCE,
                policy="core",
            )

            if is_allow(decision):
                approved += 1
            else:
                blocks_collected += 1
                print(f"\n--- BLOCK SAMPLE #{blocks_collected} ---")
                print(f"ts={ts}")
                print(f"inst={inst} side={sig.direction} strength={float(sig.strength):.4f}")
                if isinstance(decision, dict):
                    final = (decision.get("decision") or {}).get("final")
                    reason = decision.get("reason")
                    dbg = decision.get("debug")
                    print(f"final={final} reason={reason}")
                    print(f"debug={dbg}")
                    print(f"FULL_DECISION={decision}")
                else:
                    print(f"NON_DICT_DECISION={decision!r}")

                if blocks_collected >= BLOCK_SAMPLES:
                    print("\n==== STOPPING: collected requested block samples ====")
                    print(f"Signals evaluated: {signals_evaluated}")
                    print(f"Approved: {approved}")
                    print(f"Blocked: {blocks_collected}")
                    print("\nDone.")
                    return

            prev_prices[inst] = price

    print("\nReached end of timestamps.")
    print(f"Signals evaluated: {signals_evaluated}")
    print(f"Approved: {approved}")
    print(f"Blocked: {blocks_collected}")
    print("\nDone.")


if __name__ == "__main__":
    main()