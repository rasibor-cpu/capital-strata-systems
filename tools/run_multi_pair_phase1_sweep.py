"""
Phase 1 Multi-Pair Sweep (1Y M5) — Schema-Robust + Quiet
Capital Strata Systems

- Reads data/history/*_M5_1year.csv (may have different header names)
- Auto-detects price column per file
- Runs EngineLoop.process_bar(instrument, price)
- Counts rows with signal_strength (if returned)
- Suppresses noisy console spam during replay (runner-side only)
- Writes JSON report to audit_logs/phase1_multi_pair/

Replay validation only. NOT live execution.
"""

from __future__ import annotations

import csv
import json
import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


# -------------------------
# Ensure repo-root imports
# -------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


MIN_SIGNAL = 0.61
STARTING_EQUITY = 100_000
BEHAVIOUR = "D"

DATA_DIR = REPO_ROOT / "data" / "history"
OUTPUT_DIR = REPO_ROOT / "audit_logs" / "phase1_multi_pair"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRICE_CANDIDATES = [
    "close", "Close", "CLOSE", "c",
    "price", "Price",
    "mid", "Mid",
    "bid", "Bid",
    "ask", "Ask",
]


def detect_price_column(fieldnames: List[str]) -> str:
    for c in PRICE_CANDIDATES:
        if c in fieldnames:
            return c
    # fallback: last column
    return fieldnames[-1]


def read_prices(csv_path: Path) -> Dict[str, Any]:
    prices: List[float] = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"No header in {csv_path.name}")
        price_col = detect_price_column(list(reader.fieldnames))

        for row in reader:
            v = row.get(price_col, "")
            try:
                prices.append(float(v))
            except Exception:
                # last resort: try any parsable value in the row
                parsed = None
                for _, val in row.items():
                    try:
                        parsed = float(val)
                        break
                    except Exception:
                        continue
                if parsed is None:
                    raise ValueError(f"Could not parse price in {csv_path.name} using col={price_col}")
                prices.append(parsed)

    return {"prices": prices, "price_col": price_col, "fieldnames": reader.fieldnames}


def run_single_pair(csv_path: Path) -> Dict[str, Any]:
    instrument = csv_path.stem.replace("_M5_1year", "").replace("_", "")

    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    rp = read_prices(csv_path)
    prices: List[float] = rp["prices"]
    price_col: str = rp["price_col"]

    decision_is_dict = 0
    signal_rows = 0
    qualifying = 0

    # Suppress noisy prints from inside engine during replay
    with contextlib.redirect_stdout(io.StringIO()):
        for price in prices:
            decision = engine.process_bar(instrument, price)
            if isinstance(decision, dict):
                decision_is_dict += 1
                if "signal_strength" in decision:
                    signal_rows += 1
                    if float(decision.get("signal_strength", 0.0)) >= MIN_SIGNAL:
                        qualifying += 1

    summary = engine.summary() if hasattr(engine, "summary") else {}

    return {
        "instrument": instrument,
        "csv": csv_path.name,
        "price_col": price_col,
        "bars": len(prices),
        "decision_dict_rows": decision_is_dict,
        "signal_strength_rows": signal_rows,
        "qualifying_signals_ge_minsig": qualifying,
        "summary_keys": list(summary.keys()) if isinstance(summary, dict) else [],
    }


def main():
    files = sorted(DATA_DIR.glob("*_M5_1year.csv"))
    if not files:
        raise SystemExit(f"No files found in {DATA_DIR}")

    results = []

    for file in files:
        print(f"Running {file.name} ...")
        results.append(run_single_pair(file))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_DIR / f"phase1_multi_pair_{ts}.json"

    with open(out, "w") as f:
        json.dump(
            {
                "meta": {
                    "min_signal": MIN_SIGNAL,
                    "behaviour": BEHAVIOUR,
                    "starting_equity": STARTING_EQUITY,
                    "files": [p.name for p in files],
                    "generated_utc": ts,
                },
                "results": results,
            },
            f,
            indent=2,
        )

    print("\n==== COMPLETE ====\n")
    print(f"Saved: {out}\n")

    for r in results:
        print(
            f"{r['instrument']:>6} | col={r['price_col']:<8} | bars={r['bars']} | "
            f"dict={r['decision_dict_rows']} | strength_rows={r['signal_strength_rows']} | "
            f"q>={MIN_SIGNAL}={r['qualifying_signals_ge_minsig']}"
        )


if __name__ == "__main__":
    main()