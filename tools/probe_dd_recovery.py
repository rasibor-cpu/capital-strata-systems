"""
Probe: Does engine recover after hard DD?
"""

from __future__ import annotations

import csv
import sys
import io
import contextlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


PAIR = "EUR_USD_M5_1year.csv"
STARTING_EQUITY = 100_000


def detect_price_col(fields):
    for c in ("close", "price"):
        if c in fields:
            return c
    return fields[-1]


def main():
    csv_path = REPO_ROOT / "data" / "history" / PAIR
    instrument = csv_path.stem.replace("_M5_1year", "").replace("_", "")
    engine = EngineLoop(starting_equity=STARTING_EQUITY)

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        price_col = detect_price_col(reader.fieldnames)
        rows = list(reader)

    dd_triggered = False
    resumed = False

    for i, row in enumerate(rows):
        price = float(row[price_col])

        with contextlib.redirect_stdout(io.StringIO()):
            engine.process_bar(instrument, price)

        s = engine.summary()

        if not dd_triggered and s.get("gate_blocks", 0) > 1000:
            dd_triggered = True
            print(f"DD triggered at bar {i}")

        if dd_triggered:
            # check if trades resume
            if s.get("trades", 0) > 2000:
                resumed = True

    print("\nDD Triggered:", dd_triggered)
    print("Trades Resumed After DD:", resumed)


if __name__ == "__main__":
    main()