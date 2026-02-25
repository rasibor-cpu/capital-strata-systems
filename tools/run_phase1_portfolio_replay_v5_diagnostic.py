"""
Phase 1 – Portfolio Replay V5 DIAGNOSTIC (Gate Block Reasons)
Capital Strata Systems

Goal:
- Prove WHY trades=0 by sampling ExecutionGate BLOCK reasons.
- Stops after N blocked samples (fast).
- Prints decision.final, reason, and key debug fields (risk_pct, scaled_notional, governor_response, etc).

Usage:
  python tools/run_phase1_portfolio_replay_v5_diagnostic.py

Optional env overrides:
  set CSS_BEHAVIOUR=C
  set CSS_MIN_SIGNAL_STRENGTH=0.72
  set CSS_DIAG_BLOCK_SAMPLES=20
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from collections import deque, Counter
from typing import Dict, Any, List, Tuple, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine
from engine.performance.pnl_tracker import PnLTracker

# -----------------------
# Config
# -----------------------
STARTING_EQUITY = float(os.getenv("CSS_STARTING_EQUITY", "100000"))
BEHAVIOUR = str(os.getenv("CSS_BEHAVIOUR", "C")).upper().strip()
MA_WINDOW = int(os.getenv("CSS_MA_WINDOW", "20"))
STOP_DISTANCE_PCT = float(os.getenv("CSS_STOP_DISTANCE_PCT", "0.01"))
REGIME_PERSISTENCE = float(os.getenv("CSS_GATE_REGIME_PERSISTENCE", "0.95"))
MIN_SIGNAL_STRENGTH = float(os.getenv("CSS_MIN_SIGNAL_STRENGTH", "0.72"))
BLOCK_SAMPLES = int(os.getenv("CSS_DIAG_BLOCK_SAMPLES", "20"))

DATA_DIR = REPO_ROOT / "data" / "history"
PRICE_COLS = ["close", "price", "Close", "Price", "c"]
TS_COLS = ["timestamp", "time", "ts", "datetime", "Date", "date"]


def detect_col(fields: List[str], candidates: List[str]) -> str:
    for c in candidates:
        if c in fields:
            return c
    return ""


def decision_final(dec: Any) -> str:
    if not isinstance(dec, dict):
        return "NON_DICT"
    if "decision" in dec and isinstance(dec["decision"], dict):
        return str(dec["decision"].get("final", "")).upper() or "MISSING_FINAL"
    return str(dec.get("final", "")).upper() or "MISSING_FINAL"


def decision_reason(dec: Any) -> str:
    if not isinstance(dec, dict):
        return "non_dict_decision"
    if "reason" in dec:
        return str(dec["reason"])
    inner = dec.get("decision")
    if isinstance(inner, dict) and "reason" in inner:
        return str(inner["reason"])
    gov = dec.get("governor_response")
    if isinstance(gov, dict) and "reason" in gov:
        return str(gov["reason"])
    return "unknown"


def pick_debug(dec: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(dec, dict):
        return out

    dbg = dec.get("debug")
    if isinstance(dbg, dict):
        # keep only the useful keys if present
        for k in [
            "risk_pct",
            "vol_scaled_notional",
            "scaled_notional",
            "instrument",
            "side",
            "rebalance",
            "drawdown_pct",
        ]:
            if k in dbg:
                out[k] = dbg[k]

        # governor response often sits inside debug
        if "governor_response" in dbg and isinstance(dbg["governor_response"], dict):
            out["governor_response"] = {
                "ok": dbg["governor_response"].get("ok"),
                "status": dbg["governor_response"].get("status"),
                "reason": dbg["governor_response"].get("reason"),
                "risk_pct": dbg["governor_response"].get("risk_pct"),
                "recommended_notional": dbg["governor_response"].get("recommended_notional"),
            }

    # also check top-level governor_response
    gov = dec.get("governor_response")
    if isinstance(gov, dict) and "governor_response" not in out:
        out["governor_response"] = {
            "ok": gov.get("ok"),
            "status": gov.get("status"),
            "reason": gov.get("reason"),
            "risk_pct": gov.get("risk_pct"),
            "recommended_notional": gov.get("recommended_notional"),
        }

    return out


def load_all_data() -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """
    Returns:
      instrument_maps: {instrument: {timestamp: price}}
      sorted_ts: sorted list of all timestamps across instruments
    """
    instrument_maps: Dict[str, Dict[str, float]] = {}
    timestamps = set()

    files = sorted(DATA_DIR.glob("*_M5_1year.csv"))
    if not files:
        raise FileNotFoundError(f"No *_M5_1year.csv found under: {DATA_DIR}")

    for file in files:
        instrument = file.stem.replace("_M5_1year", "").replace("_", "")
        price_map: Dict[str, float] = {}

        with open(file, "r", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue

            ts_col = detect_col(reader.fieldnames, TS_COLS) or reader.fieldnames[0]
            price_col = detect_col(reader.fieldnames, PRICE_COLS) or reader.fieldnames[-1]

            for row in reader:
                ts = str(row.get(ts_col, "")).strip()
                if not ts:
                    continue
                try:
                    price = float(row[price_col])
                except Exception:
                    continue
                price_map[ts] = price
                timestamps.add(ts)

        instrument_maps[instrument] = price_map

    return instrument_maps, sorted(timestamps)


def main() -> None:
    print("\n==== PHASE 1 PORTFOLIO REPLAY V5 DIAGNOSTIC ====\n")
    print(f"BEHAVIOUR={BEHAVIOUR} | MIN_SIGNAL_STRENGTH={MIN_SIGNAL_STRENGTH} | BLOCK_SAMPLES={BLOCK_SAMPLES}\n")

    instrument_maps, sorted_ts = load_all_data()

    profile = get_profile_for_behaviour(BEHAVIOUR)
    signal_engines = {inst: SignalEngine(profile) for inst in instrument_maps.keys()}
    execution_gate = ExecutionGate()
    pnl_tracker = PnLTracker(starting_equity=STARTING_EQUITY)

    price_windows = {inst: deque(maxlen=MA_WINDOW) for inst in instrument_maps.keys()}
    prev_prices: Dict[str, float] = {}
    equity_peak = float(STARTING_EQUITY)

    blocks = 0
    block_reasons = Counter()

    total_signals = 0
    approved = 0

    for ts in sorted_ts:
        for inst, price_map in instrument_maps.items():
            price = price_map.get(ts)
            if price is None:
                continue

            price_windows[inst].append(price)

            if inst not in prev_prices:
                prev_prices[inst] = price
                continue

            if len(price_windows[inst]) < MA_WINDOW:
                prev_prices[inst] = price
                continue

            moving_avg = sum(price_windows[inst]) / len(price_windows[inst])

            signal = signal_engines[inst].generate(
                instrument=inst,
                price_now=price,
                price_prev=prev_prices[inst],
                moving_avg=moving_avg,
            )
            total_signals += 1

            if signal.direction == "FLAT":
                prev_prices[inst] = price
                continue

            if float(signal.strength) < float(MIN_SIGNAL_STRENGTH):
                prev_prices[inst] = price
                continue

            equity = float(pnl_tracker.current_equity)
            equity_peak = max(equity_peak, equity)

            decision = execution_gate.evaluate_trade(
                instrument=inst,
                side=signal.direction,
                notional=equity * 0.10,
                stop_distance_pct=float(STOP_DISTANCE_PCT),
                equity=equity,
                equity_peak=float(equity_peak),
                regime_persistence=float(REGIME_PERSISTENCE),
                policy="core",
            )

            fin = decision_final(decision)
            if fin == "ALLOW":
                approved += 1
                prev_prices[inst] = price
                continue

            # BLOCK path
            blocks += 1
            reason = decision_reason(decision)
            block_reasons[reason] += 1

            print(f"\n--- BLOCK SAMPLE #{blocks} ---")
            print(f"ts={ts}")
            print(f"inst={inst} side={signal.direction} strength={float(signal.strength):.4f}")
            print(f"final={fin} reason={reason}")

            dbg = pick_debug(decision)
            if dbg:
                print("debug:", dbg)
            else:
                print("debug: <none>")

            prev_prices[inst] = price

            if blocks >= BLOCK_SAMPLES:
                print("\n==== STOPPING: collected requested block samples ====\n")
                print(f"Signals evaluated: {total_signals}")
                print(f"Approved: {approved}")
                print(f"Blocked: {blocks}\n")
                print("Top block reasons:")
                for k, v in block_reasons.most_common(20):
                    print(f"  {k}: {v}")
                print("\nDone.")
                return

    print("\n==== COMPLETE (ran out of data before reaching block sample target) ====\n")
    print(f"Signals evaluated: {total_signals}")
    print(f"Approved: {approved}")
    print(f"Blocked: {blocks}\n")
    print("Top block reasons:")
    for k, v in block_reasons.most_common(20):
        print(f"  {k}: {v}")
    print("\nDone.")


if __name__ == "__main__":
    main()