"""
Probe: EngineLoop observability after replay (single pair)
Capital Strata Systems

Goal:
- Run a small slice of a 1Y M5 file
- Print engine.summary()
- Also print likely useful public attributes (non-private only)

This tells us exactly what we can measure for Phase 1 institutional reporting.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import List, Any
import pprint


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop  # noqa: E402


PAIR_FILE = "EUR_USD_M5_1year.csv"   # change if you want
MAX_BARS = 5000                      # small probe slice
STARTING_EQUITY = 100_000
BEHAVIOUR = "D"


def detect_price_col(fieldnames: List[str]) -> str:
    for c in ("close", "price", "Close", "Price", "c"):
        if c in fieldnames:
            return c
    return fieldnames[-1]


def main() -> None:
    csv_path = REPO_ROOT / "data" / "history" / PAIR_FILE
    instrument = csv_path.stem.replace("_M5_1year", "").replace("_", "")

    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("No header found.")
        price_col = detect_price_col(list(reader.fieldnames))

        prices: List[float] = []
        for i, row in enumerate(reader):
            if i >= MAX_BARS:
                break
            prices.append(float(row[price_col]))

    for price in prices:
        engine.process_bar(instrument, price)

    print("\n=== PROBE RESULTS ===")
    print(f"file: {PAIR_FILE}")
    print(f"instrument: {instrument}")
    print(f"bars: {len(prices)}")
    print(f"price_col: {price_col}")

    print("\n--- engine.summary() ---")
    if hasattr(engine, "summary"):
        s = engine.summary()
        pprint.pprint(s, width=120)
    else:
        print("No summary() method found.")

    print("\n--- public attributes snapshot (top-level) ---")
    # Only show simple public attributes (avoid huge objects)
    public = [a for a in dir(engine) if not a.startswith("_")]
    shortlist = []
    for a in public:
        try:
            v: Any = getattr(engine, a)
            if isinstance(v, (int, float, str, bool)) or v is None:
                shortlist.append((a, v))
        except Exception:
            pass

    for k, v in sorted(shortlist):
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()