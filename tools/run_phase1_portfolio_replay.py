"""
Phase 1 – Portfolio Mode Replay
Capital Strata Systems

Single capital pool (100k)
All instruments compete
True institutional simulation
"""

from __future__ import annotations

import csv
import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


STARTING_EQUITY = 100_000
BEHAVIOUR = "D"

DATA_DIR = REPO_ROOT / "data" / "history"
PRICE_COLS = ["close", "price", "Close", "Price", "c"]


def detect_price_col(fields):
    for c in PRICE_COLS:
        if c in fields:
            return c
    return fields[-1]


def load_all_data():
    datasets = {}
    timestamps = set()

    for file in sorted(DATA_DIR.glob("*_M5_1year.csv")):
        instrument = file.stem.replace("_M5_1year", "").replace("_", "")
        with open(file, "r", newline="") as f:
            reader = csv.DictReader(f)
            price_col = detect_price_col(reader.fieldnames)

            rows = []
            for row in reader:
                ts = row["timestamp"]
                price = float(row[price_col])
                rows.append((ts, price))
                timestamps.add(ts)

        datasets[instrument] = rows

    sorted_ts = sorted(timestamps)
    return datasets, sorted_ts


def main():
    print("\n==== PHASE 1 PORTFOLIO REPLAY ====\n")

    datasets, sorted_ts = load_all_data()

    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    instrument_maps = {}
    for inst, rows in datasets.items():
        instrument_maps[inst] = {ts: price for ts, price in rows}

    with contextlib.redirect_stdout(io.StringIO()):
        for ts in sorted_ts:
            for inst in instrument_maps:
                if ts in instrument_maps[inst]:
                    price = instrument_maps[inst][ts]
                    engine.process_bar(inst, price)

    summary = engine.summary()

    print("Portfolio Summary:")
    for k, v in summary.items():
        print(f"{k}: {v}")

    print("\nDone.")


if __name__ == "__main__":
    main()