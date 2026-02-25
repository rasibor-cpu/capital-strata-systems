from __future__ import annotations
import csv, sys, io, contextlib
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
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

def load_maps():
    instrument_maps = {}
    timestamps = set()
    for file in sorted(DATA_DIR.glob("*_M5_1year.csv")):
        inst = file.stem.replace("_M5_1year", "").replace("_", "")
        with open(file, "r", newline="") as f:
            r = csv.DictReader(f)
            pc = detect_price_col(r.fieldnames)
            m = {}
            for row in r:
                ts = row["timestamp"]
                m[ts] = float(row[pc])
                timestamps.add(ts)
        instrument_maps[inst] = m
    return instrument_maps, sorted(timestamps)

def main():
    maps, ts_list = load_maps()
    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    # snapshot initial trade_count
    last_trade_count = getattr(engine, "trade_count", 0)
    trade_by_inst = defaultdict(int)

    with contextlib.redirect_stdout(io.StringIO()):
        for ts in ts_list:
            for inst, m in maps.items():
                if ts in m:
                    engine.process_bar(inst, m[ts])
                    tc = getattr(engine, "trade_count", 0)
                    if tc > last_trade_count:
                        trade_by_inst[inst] += (tc - last_trade_count)
                        last_trade_count = tc

    print("Per-instrument trade counts:")
    for k in sorted(trade_by_inst):
        print(k, trade_by_inst[k])

    print("\nSummary:")
    print(engine.summary())

if __name__ == "__main__":
    main()