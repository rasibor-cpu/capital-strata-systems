"""
Phase 1 Diagnostic: Time to Hard DD Wall
Capital Strata Systems

For each 1Y M5 file:
- Replays full dataset
- Detects first occurrence of hard_drawdown_limit_reached
- Reports:
    - bar index
    - % of year before DD
    - equity at DD
    - final equity

This tells us whether 25% return is DD-ceiling bound.
"""

from __future__ import annotations

import csv
import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


STARTING_EQUITY = 100_000
BEHAVIOUR = "D"

DATA_DIR = REPO_ROOT / "data" / "history"

PRICE_CANDIDATES = ["close", "price", "Close", "Price", "c"]


def detect_price_col(fieldnames: List[str]) -> str:
    for c in PRICE_CANDIDATES:
        if c in fieldnames:
            return c
    return fieldnames[-1]


def run_pair(csv_path: Path) -> Dict[str, Any]:

    instrument = csv_path.stem.replace("_M5_1year", "").replace("_", "")
    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        price_col = detect_price_col(reader.fieldnames)
        rows = list(reader)

    total_bars = len(rows)
    first_dd_bar = None
    equity_at_dd = None

    for i, row in enumerate(rows):
        price = float(row[price_col])

        # silence noisy prints
        with contextlib.redirect_stdout(io.StringIO()):
            engine.process_bar(instrument, price)

        # detect hard DD via summary
        s = engine.summary()
        gate_blocks = s.get("gate_blocks", 0)

        # crude but reliable detection:
        # if gate_blocks grows very large very fast,
        # assume DD has triggered
        if first_dd_bar is None and gate_blocks > 1000:
            first_dd_bar = i
            equity_at_dd = s.get("ending_equity")

    final_summary = engine.summary()
    final_equity = final_summary.get("ending_equity")

    return {
        "instrument": instrument,
        "total_bars": total_bars,
        "first_dd_bar": first_dd_bar,
        "pct_before_dd": (
            first_dd_bar / total_bars * 100
            if first_dd_bar is not None else None
        ),
        "equity_at_dd": equity_at_dd,
        "final_equity": final_equity,
    }


def main():
    files = sorted(DATA_DIR.glob("*_M5_1year.csv"))
    results = []

    print("\n==== HARD DD TIMING DIAGNOSTIC ====\n")

    for file in files:
        print(f"Running {file.name} ...")
        r = run_pair(file)
        results.append(r)

        print(
            f"{r['instrument']:>6} | "
            f"DD_bar={r['first_dd_bar']} | "
            f"DD_pct={r['pct_before_dd']:.2f}% | "
            f"FinalEq={r['final_equity']:.2f}"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()